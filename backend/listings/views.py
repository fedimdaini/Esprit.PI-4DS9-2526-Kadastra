import re
import os

from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, IntegerField
from django.db.models.expressions import RawSQL
from .models import Data
from .serializers import DataSerializer
import requests

EUR_TO_TND   = 3.38   # approximate BCT mid-rate 2025
_CONSULT_KWS = ['consulter', 'contact', 'appeler', 'convenir', 'n/a', 'nd', 'negoci']
_COORD_RE         = re.compile(r'^-?\d{1,3}\.\d+,\s*-?\d{1,3}\.\d+$')
_ALLOWED_ORDERING = {'-date_post', 'date_post', 'prix', '-prix', '-surface', 'surface'}


# ── Price / surface helpers ───────────────────────────────────────────────
def parse_price_text(prix_text):
    """
    Returns (price_tnd: float|None, original_currency: str, is_consult: bool).
    Converts EUR → TND using EUR_TO_TND rate.
    """
    if not prix_text:
        return None, 'TND', False
    text = prix_text.strip()
    tl   = text.lower()

    if any(kw in tl for kw in _CONSULT_KWS):
        return None, 'TND', True

    is_eur = ('€' in text) or ('eur' in tl)

    digits = re.findall(r'\d[\d\s]*\d|\d', text)
    if not digits:
        return None, 'EUR' if is_eur else 'TND', False

    num_str = digits[0].replace(' ', '').replace(' ', '')
    # Normalise thousands/decimal separators
    if ',' in num_str and '.' in num_str:
        num_str = num_str.replace('.', '').replace(',', '.')
    elif ',' in num_str:
        parts = num_str.split(',')
        if len(parts[-1]) <= 2:
            num_str = num_str.replace(',', '.')
        else:
            num_str = num_str.replace(',', '')
    elif '.' in num_str:
        parts = num_str.split('.')
        if len(parts[-1]) != 2:
            num_str = num_str.replace('.', '')

    try:
        num = float(num_str)
        return (num * EUR_TO_TND, 'EUR', False) if is_eur else (num, 'TND', False)
    except ValueError:
        return None, 'EUR' if is_eur else 'TND', False


def parse_numeric_text(text):
    """Extract first integer from a text field like '3 chambres' or '120 m²'."""
    if not text:
        return None
    nums = re.findall(r'\d+', str(text))
    return int(nums[0]) if nums else None


def _is_coordinate(loc: str) -> bool:
    return bool(loc and _COORD_RE.match(loc.strip()))


# ── PostgreSQL annotation SQL ─────────────────────────────────────────────
_PRICE_SQL   = ("CASE WHEN prix ~ '[0-9]' "
                "THEN CAST(NULLIF(REGEXP_REPLACE(prix,'[^0-9]','','g'),'') AS BIGINT) "
                "ELSE NULL END")
_SURFACE_SQL = ("CASE WHEN surface ~ '[0-9]' "
                "THEN CAST(NULLIF(REGEXP_REPLACE(surface,'[^0-9]','','g'),'') AS INTEGER) "
                "ELSE NULL END")
_CHAMBRES_SQL= ("CASE WHEN chambres ~ '[0-9]' "
                "THEN CAST(NULLIF(REGEXP_REPLACE(chambres,'[^0-9]','','g'),'') AS INTEGER) "
                "ELSE NULL END")


# ── Price field enrichment ────────────────────────────────────────────────
def _enrich_price_fields(results):
    """
    Adds computed price fields to each serialised listing dict:
      price_numeric     — parsed numeric value in TND (None if no price / Prix à consulter)
      original_currency — 'EUR' or 'TND'
      is_price_consult  — True when the listing explicitly hides its price
      is_ai_price       — always False; AI estimates are the chatbot's job, not the listing page's
      surface_numeric   — parsed surface in m²

    Listings page rule: show only the original price from the database.
    "Prix à consulter" stays as-is. No ML estimates are injected here.
    """
    for r in results:
        price_tnd, currency, is_consult = parse_price_text(r.get('prix') or '')
        r['price_numeric']     = round(price_tnd) if price_tnd else None
        r['original_currency'] = currency
        r['is_price_consult']  = is_consult
        r['is_ai_price']       = False
        r['surface_numeric']   = parse_numeric_text(r.get('surface') or '')
    return results


# ── Views ─────────────────────────────────────────────────────────────────
@require_http_methods(["GET"])
def listings_view(request):
    queryset = Data.objects.all()

    # Text filters
    search       = request.GET.get('search', '')
    type_bien    = request.GET.get('type_bien', '')
    localisation = request.GET.get('localisation', '')
    source       = request.GET.get('source', '')

    if search:
        queryset = queryset.filter(
            Q(titre__icontains=search)       |
            Q(description__icontains=search) |
            Q(adresse__icontains=search)     |
            Q(localisation__icontains=search)
        )
    if type_bien and type_bien != 'all':
        queryset = queryset.filter(type__icontains=type_bien)
    if localisation and localisation != 'all':
        queryset = queryset.filter(
            Q(localisation__icontains=localisation) |
            Q(adresse__icontains=localisation)
        )
    if source and source != 'all':
        queryset = queryset.filter(lien__icontains=source)

    # Ordering param (validated)
    ordering = request.GET.get('ordering', '-date_post')
    if ordering not in _ALLOWED_ORDERING:
        ordering = '-date_post'

    # Numeric annotation + filters (PostgreSQL)
    try:
        queryset = queryset.annotate(
            price_num    = RawSQL(_PRICE_SQL,    [], output_field=IntegerField()),
            surface_num  = RawSQL(_SURFACE_SQL,  [], output_field=IntegerField()),
            chambres_num = RawSQL(_CHAMBRES_SQL, [], output_field=IntegerField()),
        )

        def _to_int(v):
            try:    return int(float(v))
            except: return None

        min_prix    = _to_int(request.GET.get('min_prix'))
        max_prix    = _to_int(request.GET.get('max_prix'))
        min_surface = _to_int(request.GET.get('min_surface'))
        max_surface = _to_int(request.GET.get('max_surface'))
        chambres    = _to_int(request.GET.get('chambres'))

        if min_prix    is not None: queryset = queryset.filter(price_num__gte=min_prix)
        if max_prix    is not None: queryset = queryset.filter(price_num__lte=max_prix)
        if min_surface is not None: queryset = queryset.filter(surface_num__gte=min_surface)
        if max_surface is not None: queryset = queryset.filter(surface_num__lte=max_surface)
        if chambres    is not None: queryset = queryset.filter(chambres_num__gte=chambres)

        # Map front-end ordering keys to annotated DB columns
        db_order_map = {
            'prix': 'price_num', '-prix': '-price_num',
            'surface': 'surface_num', '-surface': '-surface_num',
        }
        queryset = queryset.order_by(db_order_map.get(ordering, ordering))

    except Exception:
        # Fallback for non-PostgreSQL (SQLite in tests, etc.)
        queryset = queryset.order_by(ordering)

    # Pagination
    page_size = max(1, min(int(request.GET.get('page_size', 12)), 100))
    page      = max(1, int(request.GET.get('page', 1)))
    paginator = Paginator(queryset, page_size)
    page_obj  = paginator.get_page(page)

    results = list(DataSerializer(page_obj, many=True).data)
    results = _enrich_price_fields(results)

    return JsonResponse({
        'count':    paginator.count,
        'next':     page_obj.has_next() and page + 1 or None,
        'previous': page_obj.has_previous() and page - 1 or None,
        'results':  results,
    })


@require_http_methods(["GET"])
def listing_detail_view(request, pk):
    try:
        listing = Data.objects.get(pk=pk)
        data = dict(DataSerializer(listing).data)
        price_tnd, currency, is_consult = parse_price_text(data.get('prix') or '')
        data['price_numeric']     = round(price_tnd) if price_tnd else None
        data['original_currency'] = currency
        data['is_price_consult']  = is_consult
        data['is_ai_price']       = False
        data['surface_numeric']   = parse_numeric_text(data.get('surface') or '')
        return JsonResponse(data)
    except Data.DoesNotExist:
        return JsonResponse({'error': 'Annonce introuvable'}, status=404)


@require_http_methods(["GET"])
def stats_view(request):
    return JsonResponse({'total_listings': Data.objects.count()})


@require_http_methods(["GET"])
def filter_options_view(request):
    types = list(
        Data.objects
            .exclude(type__isnull=True).exclude(type__exact='')
            .values_list('type', flat=True).distinct()[:50]
    )

    raw_loc  = Data.objects.exclude(localisation__isnull=True).exclude(localisation__exact='') \
                           .values_list('localisation', flat=True).distinct()[:500]
    raw_addr = Data.objects.exclude(adresse__isnull=True).exclude(adresse__exact='') \
                           .values_list('adresse', flat=True).distinct()[:500]

    seen   = set()
    cities = []
    for loc in list(raw_loc) + list(raw_addr):
        if not loc:
            continue
        loc = loc.strip()
        # Reject coordinates, too-short/long strings, mostly-numeric strings
        if (_is_coordinate(loc)
                or len(loc) < 3
                or len(loc) > 60
                or sum(c.isdigit() for c in loc) > len(loc) * 0.4):
            continue
        key = loc.lower()
        if key not in seen:
            seen.add(key)
            cities.append(loc)
        if len(cities) >= 150:
            break

    return JsonResponse({'types': types, 'cities': sorted(cities)})


@require_http_methods(["GET"])
def proxy_image_view(request, listing_id, image_num, extension):
    url = (
        f"https://sami-scraping.duckdns.org:443/images"
        f"/{listing_id}/image_{image_num}.{extension}"
    )
    try:
        response = requests.get(url, timeout=5, verify=False)
        if response.status_code == 200:
            ct = 'image/avif' if extension == 'avif' else 'image/jpeg'
            return HttpResponse(response.content, content_type=ct)
    except Exception:
        pass
    return HttpResponse(status=404)
