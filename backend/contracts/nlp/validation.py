"""
NLP 7 — Contract validation: NER + obligations + legal refs + amounts.
Goes beyond simple keyword matching with full NLP analysis.
"""
import re
from .config import CLAUSE_CHECKS, OBLIGATION_PATTERNS
from .pos_obligations import extract_obligations_from_text


def validate_contract_nlp(contract_text, contract_type='vente'):
    """
    Full NLP validation of a generated contract.
    
    Analyzes:
    1. Critical entity presence (parties, locations, amounts) via NER
    2. Mandatory clauses via NER + semantic search
    3. Legal obligations: doit / est tenu / s'engage (syntactic deps)
    4. Amount coherence (DT, figures)
    5. Legal article citations (COC, Loi 77-40, etc.)
    """
    from .ner import get_nlp

    nlp = get_nlp()
    doc = nlp(contract_text[:5000])

    report = {
        'contract_type': contract_type,
        'nlp_entities': {},
        'clauses_nlp': {},
        'obligations_found': [],
        'legal_refs_found': [],
        'amount_check': {},
        'parties_check': {},
        'score_nlp': 0,
        'max_score_nlp': 0,
        'issues': [],
        'strengths': [],
    }

    # 1. NER extraction on generated contract
    parties = [e.text for e in doc.ents if e.label_ in ('PER', 'PERSON')]
    lieux = [e.text for e in doc.ents if e.label_ in ('LOC', 'GPE')]
    montants = [e.text for e in doc.ents if e.label_ in ('MONEY', 'CARDINAL', 'QUANTITY')]
    legal_docs = [e.text for e in doc.ents if e.label_ == 'LEGAL_DOC']
    biens = [e.text for e in doc.ents if e.label_ == 'PROPERTY']

    report['nlp_entities'] = {
        'parties': parties[:5],
        'lieux': lieux[:5],
        'montants': montants[:5],
        'legal_docs': legal_docs[:3],
        'biens': biens[:3],
    }

    # 2. Mandatory clause checks (NER + keywords)
    contract_lower = contract_text.lower()

    clause_checks_def = CLAUSE_CHECKS.get(contract_type, CLAUSE_CHECKS['vente'])
    selected_clauses = {}
    for clause_name, keywords in clause_checks_def.items():
        selected_clauses[clause_name] = any(k in contract_lower for k in keywords)

    # Enrich with NER results
    if contract_type in ('vente', 'terrain'):
        if bool(parties):
            selected_clauses['Identification'] = True
        if bool(biens):
            selected_clauses['Description'] = True
        if bool(montants):
            selected_clauses['Prix'] = True
        if bool(legal_docs):
            if 'Cadastre' in selected_clauses:
                selected_clauses['Cadastre'] = True

    elif contract_type == 'location':
        if bool(parties):
            selected_clauses['Identification'] = True
        if bool(biens):
            selected_clauses['Description'] = True
        if bool(montants):
            selected_clauses['Loyer'] = True

    report['clauses_nlp'] = selected_clauses
    clauses_ok = sum(selected_clauses.values())
    clauses_total = len(selected_clauses)

    # 3. Legal obligations via syntactic dependencies
    obligations = extract_obligations_from_text(contract_text[:3000])
    report['obligations_found'] = obligations[:5]
    has_obligations = len(obligations) >= 3

    # 4. Legal references cited
    legal_ref_patterns = [
        r'art(?:icle)?\.?\s*\d+\s+(?:coc|cod)',
        r'loi\s+(?:n°\s*)?\d+[-–]\d+',
        r'code\s+des\s+obligations',
        r'décret(?:-loi)?\s+\d+',
        r'art(?:icle)?\.?\s+\d+',
    ]
    legal_refs = []
    for pat in legal_ref_patterns:
        found = re.findall(pat, contract_text.lower())
        legal_refs.extend(found[:2])
    report['legal_refs_found'] = list(set(legal_refs))[:6]
    has_legal_refs = len(legal_refs) >= 2

    # 5. Amount verification
    amounts_in_text = re.findall(
        r'\d[\d\s,.]*(?:dt|dinar|dinars)', contract_text.lower()
    )
    amount_in_letters = bool(re.search(
        r'(?:mille|cent|vingt|trente|quarante|cinquante|soixante|dix|onze|douze)'
        r'\s+dinars',
        contract_text.lower()
    ))
    report['amount_check'] = {
        'amounts_found': amounts_in_text[:4],
        'amount_in_letters': amount_in_letters,
        'ok': bool(amounts_in_text),
    }

    # 6. Parties identified by NER
    has_two_parties = len(set(parties)) >= 2
    report['parties_check'] = {
        'parties_found': parties[:4],
        'has_two_parties': has_two_parties,
    }

    # ── NLP Scoring ────────────────────────────────────────────────────────────
    score = 0
    max_score = clauses_total + 5

    score += clauses_ok
    if has_obligations:
        score += 1
    if has_legal_refs:
        score += 1
    if report['amount_check']['ok']:
        score += 1
    if has_two_parties:
        score += 1
    if amount_in_letters:
        score += 1

    report['score_nlp'] = score
    report['max_score_nlp'] = max_score
    report['ccr_nlp'] = round(score / max_score * 100, 1) if max_score > 0 else 0

    # ── Issues and Strengths ──────────────────────────────────────────────────
    for clause_name, present in selected_clauses.items():
        if not present:
            report['issues'].append(f'Clause manquante : {clause_name}')
        else:
            report['strengths'].append(f'✓ {clause_name}')
    if not has_obligations:
        report['issues'].append('Moins de 3 obligations légales détectées')
    if not has_legal_refs:
        report['issues'].append('Aucune référence à un article de loi')
    if not has_two_parties:
        report['issues'].append('Moins de 2 parties identifiées par NER')

    return report
