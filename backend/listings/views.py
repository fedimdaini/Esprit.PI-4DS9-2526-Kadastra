from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Data
from .serializers import DataSerializer
import requests

@require_http_methods(["GET"])
def listings_view(request):
    queryset = Data.objects.all()
    
    # Filtres
    search = request.GET.get('search', '')
    type_bien = request.GET.get('type_bien', '')
    localisation = request.GET.get('localisation', '')
    
    if search:
        queryset = queryset.filter(Q(titre__icontains=search) | Q(description__icontains=search))
    if type_bien and type_bien != 'all':
        queryset = queryset.filter(type__icontains=type_bien)
    if localisation and localisation != 'all':
        queryset = queryset.filter(localisation__icontains=localisation)
    
    # Tri
    ordering = request.GET.get('ordering', '-date_post')
    queryset = queryset.order_by(ordering)
    
    # Pagination
    page_size = int(request.GET.get('page_size', 12))
    page = int(request.GET.get('page', 1))
    
    paginator = Paginator(queryset, page_size)
    page_obj = paginator.get_page(page)
    
    serializer = DataSerializer(page_obj, many=True)
    
    return JsonResponse({
        'count': paginator.count,
        'next': page_obj.has_next() and page + 1 or None,
        'previous': page_obj.has_previous() and page - 1 or None,
        'results': serializer.data
    })


@require_http_methods(["GET"])
def listing_detail_view(request, pk):
    try:
        listing = Data.objects.get(pk=pk)
        serializer = DataSerializer(listing)
        return JsonResponse(serializer.data)
    except Data.DoesNotExist:
        return JsonResponse({'error': 'Annonce introuvable'}, status=404)


@require_http_methods(["GET"])
def stats_view(request):
    total = Data.objects.count()
    return JsonResponse({'total_listings': total})


@require_http_methods(["GET"])
def filter_options_view(request):
    types = list(Data.objects.exclude(type__isnull=True).values_list('type', flat=True).distinct()[:50])
    cities = list(Data.objects.exclude(localisation__isnull=True).values_list('localisation', flat=True).distinct()[:100])
    
    return JsonResponse({
        'types': types,
        'cities': cities
    })


@require_http_methods(["GET"])
def proxy_image_view(request, listing_id, image_num, extension):
    """
    Proxy pour servir les images via Django
    GET /api/images/{listing_id}/{image_num}/{extension}/
    Extension: 'avif' pour Mubawab, 'jpg' pour Tayara
    """
    url = f"https://sami-scraping.duckdns.org:443/images/{listing_id}/image_{image_num}.{extension}"
    try:
        
        response = requests.get(url, timeout=5, verify=False)
        if response.status_code == 200:
            content_type = 'image/avif' if extension == 'avif' else 'image/jpeg'
            
            return HttpResponse(response.content, content_type=content_type)
    except:
        pass
    
    return HttpResponse(status=404)