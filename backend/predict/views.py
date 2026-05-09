"""
predict/views.py — Market trend forecast endpoint.

Reads pre-generated CSV files (ts_trend_scores_{type}_{transaction}.csv)
from predict/data/ and returns per-governorate 12-month forecasts for all
24 Tunisian governorates. Missing governorates are filled with regional then
national averages and flagged as estimated=True.
"""
import os
import csv
from collections import defaultdict
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt

# ── Constants ─────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

ALL_GOVERNORATES = [
    'Tunis', 'Ariana', 'Ben Arous', 'Manouba', 'Nabeul', 'Zaghouan',
    'Bizerte', 'Beja', 'Jendouba', 'Kef', 'Siliana',
    'Sousse', 'Monastir', 'Mahdia', 'Sfax',
    'Kairouan', 'Kasserine', 'Sidi Bouzid',
    'Gabes', 'Mednine', 'Tataouine', 'Gafsa', 'Tozeur', 'Kebili',
]

REGIONS = {
    'north':       ['Tunis', 'Ariana', 'Ben Arous', 'Manouba', 'Nabeul',
                    'Zaghouan', 'Bizerte', 'Beja', 'Jendouba', 'Kef', 'Siliana'],
    'centre_east': ['Sousse', 'Monastir', 'Mahdia', 'Sfax'],
    'centre_west': ['Kairouan', 'Kasserine', 'Sidi Bouzid'],
    'south':       ['Gabes', 'Mednine', 'Tataouine', 'Gafsa', 'Tozeur', 'Kebili'],
}

GOV_TO_REGION = {g: r for r, gs in REGIONS.items() for g in gs}

# Normalise non-standard names in CSVs → canonical governorate names
CSV_NAME_MAP = {
    'Medenine': 'Mednine',   # spelling variant
    'Lac':      'Tunis',     # Lac de Tunis neighbourhood → Tunis gov.
    'La Marsa': 'Ariana',    # coastal suburb → Ariana gov.
}

TYPE_KEY_MAP = {
    'appartement': 'appt',
    'maison':      'maison',
    'terrain':     'terrain',
    'local':       'local',
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def _trend_label(pct):
    if pct > 3:
        return 'hausse'
    if pct < -3:
        return 'baisse'
    return 'stable'


def _avg(values):
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _read_csv(type_bien, transaction):
    """
    Read and normalise a trend CSV.
    Returns {canonical_gov: {trend_pct, current_price_m2, future_price_m2}}.
    Duplicate rows (after normalisation) are averaged.
    """
    type_key = TYPE_KEY_MAP.get(type_bien, 'appt')
    csv_path = os.path.join(DATA_DIR, f'ts_trend_scores_{type_key}_{transaction}.csv')
    if not os.path.exists(csv_path):
        return {}

    buckets = defaultdict(list)
    with open(csv_path, newline='', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            name = CSV_NAME_MAP.get(row['governorate'], row['governorate'])
            pct   = float(row['forecast_12m_pct_change'])
            price_raw = row.get('last_actual_price', '').strip()
            price = float(price_raw) if price_raw else None
            buckets[name].append({'pct': pct, 'price': price})

    result = {}
    for gov, entries in buckets.items():
        if gov not in ALL_GOVERNORATES:
            continue
        avg_pct   = _avg([e['pct']   for e in entries])
        avg_price = _avg([e['price'] for e in entries])
        avg_future = avg_price * (1 + avg_pct / 100) if avg_price is not None else None
        result[gov] = {
            'trend_pct':        round(avg_pct,    2),
            'current_price_m2': round(avg_price,  2) if avg_price  is not None else None,
            'future_price_m2':  round(avg_future, 2) if avg_future is not None else None,
        }
    return result


# ── View ──────────────────────────────────────────────────────────────────────
@csrf_exempt
@require_http_methods(['GET'])
def forecast_map(request):
    """
    GET /api/predict/forecast/map/
    Params: type_bien (appartement|maison|terrain|local)
            transaction (vente|location)
    """
    type_bien   = request.GET.get('type_bien',   'appartement')
    transaction = request.GET.get('transaction', 'vente')

    real = _read_csv(type_bien, transaction)

    # ── Regional averages (from real data in that region) ────────────────────
    regional = {}
    for region, govs in REGIONS.items():
        members = [g for g in govs if g in real]
        if not members:
            continue
        avg_pct   = _avg([real[g]['trend_pct']        for g in members])
        avg_price = _avg([real[g]['current_price_m2'] for g in members])
        avg_future = round(avg_price * (1 + avg_pct / 100), 2) if avg_price else None
        regional[region] = {
            'trend_pct':        round(avg_pct, 2),
            'current_price_m2': round(avg_price, 2) if avg_price else None,
            'future_price_m2':  avg_future,
        }

    # ── National fallback ────────────────────────────────────────────────────
    if real:
        nat_pct   = _avg([d['trend_pct']        for d in real.values()])
        nat_price = _avg([d['current_price_m2'] for d in real.values()])
        national  = {
            'trend_pct':        round(nat_pct, 2),
            'current_price_m2': round(nat_price, 2) if nat_price else None,
            'future_price_m2':  round(nat_price * (1 + nat_pct / 100), 2) if nat_price else None,
        }
    else:
        national = {'trend_pct': 0, 'current_price_m2': None, 'future_price_m2': None}

    # ── Build full 24-governorate result ─────────────────────────────────────
    results = []
    for gov in ALL_GOVERNORATES:
        if gov in real:
            d = real[gov]
            results.append({
                'gouvernorat':      gov,
                'trend':            _trend_label(d['trend_pct']),
                'trend_pct':        d['trend_pct'],
                'current_price_m2': d['current_price_m2'],
                'future_price_m2':  d['future_price_m2'],
                'estimated':        False,
            })
        else:
            region   = GOV_TO_REGION.get(gov)
            fallback = regional.get(region, national)
            results.append({
                'gouvernorat':      gov,
                'trend':            _trend_label(fallback['trend_pct']),
                'trend_pct':        fallback['trend_pct'],
                'current_price_m2': fallback.get('current_price_m2'),
                'future_price_m2':  fallback.get('future_price_m2'),
                'estimated':        True,
            })

    return JsonResponse({
        'type_bien':   type_bien,
        'transaction': transaction,
        'results':     results,
    })
