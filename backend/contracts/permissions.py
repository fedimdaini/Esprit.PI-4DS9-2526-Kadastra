"""
Role-based permissions for contract generation.
Maps Django User.user_type to notebook permission system.
"""
from .nlp.config import USER_PERMISSIONS


# Map Django user_type to notebook role keys
ROLE_MAP = {
    'PARTICULIER': 'particulier_acheteur',
    'INVESTISSEUR': 'investisseur',
    'AGENT': 'agent',
    'BANQUIER': 'banquier',
}

ROLE_LABELS = {
    'particulier_acheteur': 'Particulier — Acheteur/Locataire',
    'particulier_vendeur': 'Particulier — Vendeur/Bailleur',
    'investisseur': 'Investisseur',
    'agent': 'Agent Immobilier',
    'banquier': 'Banquier',
}

ROLE_RESTRICTIONS = {
    'particulier_acheteur': 'Lecture seule sur prix et clauses financières.',
    'particulier_vendeur': 'Peut définir prix et conditions. Ne peut pas modifier clauses légales obligatoires.',
    'investisseur': 'Peut modifier conditions financières. Ne peut pas accéder aux clauses bancaires.',
    'agent': 'Accès complet à toutes les clauses.',
    'banquier': 'Accès uniquement aux clauses financières et hypothèques.',
}


def get_nlp_role(user, context=None):
    """
    Convert Django user to NLP role key.
    If Particular, can be 'particulier_acheteur' or 'particulier_vendeur'.
    """
    if user is None or not hasattr(user, 'user_type'):
        return 'particulier_acheteur'
    
    u_type = user.user_type
    if u_type == 'PARTICULIER':
        if context == 'vendeur':
            return 'particulier_vendeur'
        return 'particulier_acheteur'
    
    return ROLE_MAP.get(u_type, 'particulier_acheteur')


def get_permission_prompt(user_role, contract_type):
    """Build the permission section for the LLM prompt."""
    perms = USER_PERMISSIONS.get(user_role, {}).get(contract_type, [])
    label = ROLE_LABELS.get(user_role, user_role)
    restr = ROLE_RESTRICTIONS.get(user_role, '')

    if not perms:
        return (
            f'ROLE : {label}\n'
            f'PERMISSIONS : Lecture seule pour {contract_type}.\n'
            f'RESTRICTIONS : {restr}'
        )
    if 'ALL' in perms:
        return (
            f'ROLE : {label}\n'
            f'PERMISSIONS : Accès complet.\n'
            f'RESTRICTIONS : {restr}'
        )
    return (
        f'ROLE : {label}\n'
        f'PERMISSIONS : {", ".join(perms)} uniquement.\n'
        f'RESTRICTIONS : {restr}'
    )


def get_user_permissions_info(user_role, contract_type):
    """Get structured permissions info for the API response."""
    perms = USER_PERMISSIONS.get(user_role, {}).get(contract_type, [])
    label = ROLE_LABELS.get(user_role, user_role)

    if 'ALL' in perms:
        perm_str = 'TOUTES'
    elif perms:
        perm_str = ', '.join(perms)
    else:
        perm_str = 'LECTURE SEULE'

    return {
        'role': user_role,
        'role_label': label,
        'permissions': perms,
        'permissions_display': perm_str,
        'restriction': ROLE_RESTRICTIONS.get(user_role, ''),
    }
