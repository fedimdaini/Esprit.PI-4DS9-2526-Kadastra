import os
import json
import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

KADASTRA_ML_URL = os.environ.get("KADASTRA_ML_URL", "http://localhost:8001")


@csrf_exempt
@require_http_methods(["POST"])
def analyze(request):
    """Proxy POST /api/kadastra/analyze → ML service /api/analyze"""
    try:
        body = json.loads(request.body)
        resp = requests.post(f"{KADASTRA_ML_URL}/api/analyze", json=body, timeout=120)
        return JsonResponse(resp.json(), status=resp.status_code)
    except requests.Timeout:
        return JsonResponse({"error": "ML service timeout"}, status=504)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=502)


@csrf_exempt
@require_http_methods(["POST"])
def quick_analyze(request):
    """Proxy POST /api/kadastra/quick-analyze → ML service /api/quick-analyze"""
    try:
        body = json.loads(request.body)
        resp = requests.post(f"{KADASTRA_ML_URL}/api/quick-analyze", json=body, timeout=120)
        return JsonResponse(resp.json(), status=resp.status_code)
    except requests.Timeout:
        return JsonResponse({"error": "ML service timeout"}, status=504)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=502)


@require_http_methods(["GET"])
def health(request):
    """Proxy GET /api/kadastra/health → ML service /api/health"""
    try:
        resp = requests.get(f"{KADASTRA_ML_URL}/api/health", timeout=5)
        return JsonResponse(resp.json(), status=resp.status_code)
    except Exception as e:
        return JsonResponse({"error": str(e), "status": "unreachable"}, status=502)
