"""
Contract API Views — REST endpoints for contract generation, chat, PDF, and report.
"""
import json
import os

from django.shortcuts import render
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.views.decorators.clickjacking import xframe_options_exempt

from listings.models import Data

from .nlp.pipeline import (
    detect_contract_type,
    build_advanced_prompt,
    evaluate_contract_quality,
)
from .nlp.correction import post_correct_contract
from .nlp.validation import validate_contract_nlp
from .llm import call_llm, get_best_model
from .permissions import (
    get_nlp_role,
    get_permission_prompt,
    get_user_permissions_info,
)
from .pdf_generator import generate_pdf_contract


def _listing_to_dict(data_obj):
    """Convert a Data model instance to a dict matching notebook format."""
    return {
        'id': data_obj.id,
        'titre': data_obj.titre or '',
        'prix': data_obj.prix or '',
        'adresse': data_obj.adresse or '',
        'localisation': data_obj.localisation or '',
        'description': data_obj.description or '',
        'pieces': data_obj.pieces or '',
        'surface': data_obj.surface or '',
        'type': data_obj.type or '',
    }


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def generate_contract_view(request):
    """
    POST /api/contracts/generate/
    Body: {
        "listing_id": int,
        "contract_type": "vente"|"location"|"terrain" (optional, auto-detected),
        "vendeur_info": {"nom": str, "cin": str, "adresse": str} (optional)
    }
    
    Generates a contract using the best LLM with all 7 NLP modules.
    """
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    listing_id = data.get('listing_id')
    if not listing_id:
        return JsonResponse({'error': 'listing_id is required'}, status=400)

    # Fetch listing from DB
    try:
        listing_obj = Data.objects.using('kadastra').get(pk=listing_id)
    except Data.DoesNotExist:
        return JsonResponse({'error': 'Listing not found'}, status=404)

    listing = _listing_to_dict(listing_obj)

    # Contract type
    contract_type = data.get('contract_type') or detect_contract_type(listing)

    # Party info — trust the frontend's role-based assignment
    vendeur_info = data.get('vendeur_info')
    acheteur_info = data.get('acheteur_info')

    # Fallback: if no acheteur_info AND no vendeur_info provided, use logged-in user
    if request.user.is_authenticated:
        role_ctx = data.get('role_context', 'acheteur')
        user_profile = {
            'nom': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
            'cin': getattr(request.user, 'cin', ''),
            'adresse': getattr(request.user, 'address', ''),
        }
        if role_ctx == 'vendeur' and (not vendeur_info or not vendeur_info.get('nom')):
            vendeur_info = user_profile
        elif role_ctx == 'acheteur' and (not acheteur_info or not acheteur_info.get('nom')):
            acheteur_info = user_profile

    # Build NLP-enriched prompt
    user_role = get_nlp_role(
        request.user if request.user.is_authenticated else None,
        context=data.get('role_context')
    )
    perm_prompt = get_permission_prompt(user_role, contract_type)

    system_prompt, user_message, entities = build_advanced_prompt(
        listing, contract_type, vendeur_info, acheteur_info, perm_prompt
    )

    # Get best model
    best = get_best_model()
    platform = best.get('platform', 'esprit')
    model_id = best.get('model_id')

    # Generate contract via LLM
    try:
        contract, elapsed, tokens = call_llm(
            system_prompt, user_message,
            platform=platform, model_id=model_id, max_tokens=3000
        )
    except Exception as e:
        return JsonResponse({
            'error': f'LLM generation failed: {str(e)}'
        }, status=502)

    # NLP 5: Post-correction
    contract_corrected = post_correct_contract(contract)

    # NLP 7: Validation
    nlp_report = validate_contract_nlp(contract_corrected, contract_type)

    # Combined evaluation
    evaluation = evaluate_contract_quality(contract_corrected, contract_type)

    # User role permissions
    user_role = get_nlp_role(
        request.user if request.user.is_authenticated else None
    )
    permissions_info = get_user_permissions_info(user_role, contract_type)

    return JsonResponse({
        'contract': contract_corrected,
        'contract_type': contract_type,
        'listing_id': listing_id,
        'model': best.get('best_model_label', model_id),
        'generation_time': elapsed,
        'tokens_used': tokens,
        'evaluation': {
            'ccr_combined': evaluation['clean_contract_rate'],
            'kw_ccr': evaluation['kw_ccr'],
            'nlp_ccr': evaluation['nlp_ccr'],
            'error_rate': evaluation['error_rate'],
            'clauses_found': evaluation['clauses_found'],
            'clauses_total': evaluation['clauses_total'],
            'missing_clauses': evaluation['missing_clauses'],
            'is_clean': evaluation['is_clean'],
        },
        'nlp_report': {
            'ccr_nlp': nlp_report['ccr_nlp'],
            'score': nlp_report['score_nlp'],
            'max_score': nlp_report['max_score_nlp'],
            'obligations': len(nlp_report['obligations_found']),
            'legal_refs': nlp_report['legal_refs_found'],
            'issues': nlp_report['issues'],
            'strengths': nlp_report['strengths'],
            'entities': nlp_report['nlp_entities'],
            'parties': nlp_report['parties_check'],
            'amounts': nlp_report['amount_check'],
        },
        'permissions': permissions_info,
        'nlp_entities': {
            'lieux': entities.get('lieux', [])[:4],
            'biens': entities.get('biens', [])[:3],
            'montants': entities.get('montants', [])[:3],
        },
    })


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def chat_contract_view(request):
    """
    POST /api/contracts/chat/
    Body: {
        "contract_text": str,
        "question": str,
        "contract_type": "vente"|"location"|"terrain"
    }
    
    Chat about a generated contract with role-based permissions.
    """
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    contract_text = data.get('contract_text', '')
    question = data.get('question', '')
    contract_type = data.get('contract_type', 'vente')

    if not contract_text or not question:
        return JsonResponse({
            'error': 'contract_text and question are required'
        }, status=400)

    # User role
    user_role = get_nlp_role(
        request.user if request.user.is_authenticated else None
    )
    perm_prompt = get_permission_prompt(user_role, contract_type)

    system_prompt = (
        f"Tu es un AVOCAT EXPERT en droit immobilier tunisien (Cabinet KADASTRA).\n"
        f"{perm_prompt}\n\n"
        f"CONTRAT ACTUEL :\n{contract_text[:4000]}\n\n"
        "INSTRUCTIONS D'ÉDITION :\n"
        "1. Si l'utilisateur demande une modification (changement de prix, ajout de clause, correction de nom, etc.) "
        "ET que son rôle l'autorise, effectue le changement dans le texte du contrat.\n"
        "2. Dans ce cas, réponds d'abord brièvement pour confirmer le changement, puis inclus "
        "impérativement le NOUVEAU TEXTE INTÉGRAL du contrat entre les balises <updated_contract> et </updated_contract>.\n"
        "3. Si l'utilisateur pose juste une question sans demander de changement, réponds normalement sans ces balises.\n"
        "4. Respecte strictement les RESTRICTIONS du rôle."
    )

    best = get_best_model()
    try:
        answer, elapsed, tokens = call_llm(
            system_prompt, question,
            platform=best.get('platform', 'esprit'),
            model_id=best.get('model_id'),
            max_tokens=2500 # Increased to allow full contract return
        )
    except Exception as e:
        return JsonResponse({
            'error': f'Chat failed: {str(e)}'
        }, status=502)

    # Extract updated contract if present
    updated_contract = None
    if '<updated_contract>' in answer:
        parts = answer.split('<updated_contract>')
        final_parts = parts[1].split('</updated_contract>')
        updated_contract = final_parts[0].strip()
        answer = parts[0].strip() + (final_parts[1].strip() if len(final_parts) > 1 else '')

    return JsonResponse({
        'answer': answer.strip(),
        'updated_contract': updated_contract,
        'role': user_role,
        'generation_time': elapsed,
    })


@csrf_exempt
@require_http_methods(["POST", "OPTIONS"])
def download_pdf_view(request):
    """
    POST /api/contracts/pdf/
    Body: {
        "contract_text": str,
        "listing_id": int,
        "contract_type": "vente"|"location"|"terrain",
        "model_label": str (optional),
        "nlp_report": dict (optional)
    }
    
    Generate and download a PDF of the contract.
    """
    if request.method == "OPTIONS":
        return JsonResponse({}, status=200)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    contract_text = data.get('contract_text', '')
    listing_id = data.get('listing_id', 0)
    contract_type = data.get('contract_type', 'vente')
    model_label = data.get('model_label', 'LLM')
    nlp_report = data.get('nlp_report')

    if not contract_text:
        return JsonResponse({
            'error': 'contract_text is required'
        }, status=400)

    listing = {'id': listing_id}

    try:
        pdf_path = generate_pdf_contract(
            contract_text, listing, contract_type,
            model_label=model_label,
            nlp_report=nlp_report,
        )
    except Exception as e:
        return JsonResponse({
            'error': f'PDF generation failed: {str(e)}'
        }, status=500)

    return FileResponse(
        open(pdf_path, 'rb'),
        as_attachment=True,
        filename=f'contrat_{contract_type}_{listing_id}.pdf',
        content_type='application/pdf',
    )

@xframe_options_exempt
def map_view(request):
    """
    Serve the interactive incidents map.
    """
    return render(request, 'carte2.html')
