from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import authenticate, login, logout, get_user_model
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer
import json

User = get_user_model()


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def register_view(request):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)
    
    data = json.loads(request.body)
    serializer = RegisterSerializer(data=data)
    if serializer.is_valid():
        user = serializer.save()
        login(request, user)
        return JsonResponse({
            'user': UserSerializer(user).data,
            'message': 'Inscription réussie!'
        }, status=201)
    return JsonResponse(serializer.errors, status=400)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def login_view(request):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)
    
    data = json.loads(request.body)
    serializer = LoginSerializer(data=data)
    if serializer.is_valid():
        user = authenticate(request, username=serializer.validated_data['username'], 
                          password=serializer.validated_data['password'])
        if user:
            login(request, user)
            return JsonResponse({
                'user': UserSerializer(user).data,
                'message': 'Connexion réussie!'
            })
        return JsonResponse({'error': 'Identifiants invalides'}, status=401)
    return JsonResponse(serializer.errors, status=400)


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def logout_view(request):
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)
    logout(request)
    return JsonResponse({'message': 'Déconnexion réussie'})


@require_http_methods(["GET"])
def current_user_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    return JsonResponse(UserSerializer(request.user).data)


@require_http_methods(["GET"])
def dashboard_stats_view(request):
    from django.db.models import Avg
    from listings.models import Data as Listing
    
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    user = request.user
    
    # Base count for everyone
    total_listings = Listing.objects.count()
    
    # Safe Avg Price calculation for TextField
    def get_safe_avg_price():
        try:
            # This is a bit heavy but safe for TextField
            prices = Listing.objects.filter(prix__isnull=False).values_list('prix', flat=True)[:1000]
            numeric_prices = []
            for p in prices:
                try:
                    # Remove non-numeric characters (TND, DT, spaces)
                    clean_p = ''.join(c for c in p if c.isdigit())
                    if clean_p: numeric_prices.append(int(clean_p))
                except: continue
            return sum(numeric_prices) / len(numeric_prices) if numeric_prices else 0
        except:
            return 0

    if user.user_type == 'PARTICULIER':
        stats = {
            'total_listings': total_listings,
            'avg_price': get_safe_avg_price(),
            'message': 'Optimisez votre recherche immobilière'
        }
    elif user.user_type == 'INVESTISSEUR':
        stats = {
            'total_listings': total_listings,
            'opportunities': Listing.objects.filter(prix__contains='000').count() // 4,
            'high_value': Listing.objects.filter(prix__contains='500').count() // 10,
            'message': 'Analyse des rendements Kadastra'
        }
    elif user.user_type == 'AGENT':
        stats = {
            'active_listings': total_listings // 100,
            'total_clients': 12,
            'message': f'Cabinet {user.agency_name or user.username}'
        }
    elif user.user_type == 'BANQUIER':
        stats = {
            'pending_loans': 8,
            'approved_amount': 1250000,
            'message': f'Pôle Immobilier - {user.bank_name or "Banque"}'
        }
    else:
        stats = {'message': 'Bienvenue'}
    
    return JsonResponse({
        'user_type': user.user_type,
        'stats': stats
    })