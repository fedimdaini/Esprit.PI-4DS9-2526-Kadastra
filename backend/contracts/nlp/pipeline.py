"""
NLP Pipeline — Orchestrates all 7 NLP modules for contract generation.
"""
from .ner import extract_entities_advanced, get_nlp
from .lexical import transform_to_legal_terms_advanced
from .tfidf_chunks import extract_ranked_noun_chunks
from .correction import post_correct_contract
from .rag import build_rag_context
from .validation import validate_contract_nlp
from .config import CLAUSE_CHECKS


def detect_contract_type(listing):
    """Auto-detect contract type from listing data."""
    combined = ' '.join([str(v) for v in listing.values() if v]).lower()

    if any(k in combined for k in ['terrain', 'parcelle', 'lot', 'hectare',
                                    'agricole', 'constructible']):
        return 'terrain'
    if any(k in combined for k in ['location', 'louer', 'a louer', 'bail', 'loyer']):
        return 'location'

    nlp = get_nlp()
    text = ' '.join([
        str(listing.get('titre', '') or ''),
        str(listing.get('description', '') or '')[:300]
    ])
    doc = nlp(text)
    for token in doc:
        if token.lemma_.lower() in ('terrain', 'parcelle', 'lot', 'hectare'):
            return 'terrain'
        if token.lemma_.lower() in ('location', 'bail', 'loyer', 'louer'):
            return 'location'
    return 'vente'


def get_contract_title(contract_type, listing):
    """Get the formal contract title."""
    combined = ' '.join([str(v) for v in listing.values() if v]).lower()
    if contract_type == 'terrain':
        if any(k in combined for k in ['louer', 'location', 'bail']):
            return 'CONTRAT DE BAIL DE TERRAIN'
        return 'CONTRAT DE VENTE DE TERRAIN'
    titles = {
        'location': "CONTRAT DE BAIL À USAGE D'HABITATION",
        'vente': 'PROMESSE SYNALLAGMATIQUE DE VENTE',
    }
    return titles.get(contract_type, 'CONTRAT IMMOBILIER')


def format_listing_for_prompt(listing):
    """Format listing data for the LLM prompt."""
    labels = {
        'id': 'ID', 'titre': 'Titre', 'prix': 'Prix (DT)',
        'adresse': 'Adresse', 'localisation': 'Localisation',
        'description': 'Description', 'pieces': 'Pieces',
        'surface': 'Superficie (m2)', 'type': 'Type',
    }
    lines = []
    for k, v in listing.items():
        if v and str(v).strip() not in ('', 'None'):
            label = labels.get(k, k)
            lines.append(f'- {label} : {str(v)[:200]}')
    return '\n'.join(lines)


def build_advanced_prompt(listing, contract_type, vendeur_info=None, acheteur_info=None, perm_prompt=None):
    """
    Build the enriched prompt with ALL 7 NLP modules:
    NER + POS-filtered + ranked noun chunks + obligations +
    FAISS RAG + legal lexical transformation.
    """
    entities = extract_entities_advanced(listing)
    listing_info = format_listing_for_prompt(listing)
    listing_text = ' '.join([str(v) for v in listing.values() if v])

    # RAG (NLP 6)
    rag_query = f"{listing.get('titre', '')} {listing.get('localisation', '')} {contract_type}"
    rag_context = build_rag_context(rag_query, contract_type, top_k=4)

    # Noun chunks (NLP 4)
    nlp = get_nlp()
    doc_listing = nlp(listing_text[:1000])
    ranked_chunks = extract_ranked_noun_chunks(doc_listing, top_n=6)

    # Lexical transformation (NLP 2)
    titre_transformed, _ = transform_to_legal_terms_advanced(
        listing.get('titre', '') or ''
    )

    nlp_section = f'''ANALYSE NLP AVANCÉE (spaCy fr_lg + TF-IDF + FAISS) :
- Lieux (NER+POS) : {', '.join(entities['lieux'][:4]) or 'non détecté'}
- Biens (PROPERTY) : {', '.join(entities['biens'][:3]) or 'non détecté'}
- Montants (NER) : {', '.join(entities['montants'][:3]) or 'non détecté'}
- Docs légaux : {', '.join(entities['docs_legaux'][:3]) or 'non détecté'}
- Syntagmes clés (TF-IDF) : {', '.join([c['text'] for c in ranked_chunks[:4]]) or 'aucun'}
- Verbes d'action : {', '.join(entities['verbes_cles'][:5]) or 'aucun'}
- Obligations détectées : {len(entities['obligations'])} clause(s)
- Titre transformé : {titre_transformed[:80]}'''

    vendeur_block = (
        f"VENDEUR : {vendeur_info['nom']} | CIN : {vendeur_info['cin']} | "
        f"Adresse : {vendeur_info['adresse']}"
        if vendeur_info and vendeur_info.get('nom')
        else 'VENDEUR : [NOM DU VENDEUR] | CIN : [CIN VENDEUR] | Adresse : [ADRESSE VENDEUR]'
    )

    acheteur_label = "ACQUÉREUR" if contract_type == 'vente' else "LOCATAIRE"
    acheteur_block = (
        f"{acheteur_label} : {acheteur_info['nom']} | CIN : {acheteur_info['cin']} | "
        f"Adresse : {acheteur_info['adresse']}"
        if acheteur_info and acheteur_info.get('nom')
        else f'{acheteur_label} : [NOM DU CLIENT] | CIN : [CIN CLIENT] | Adresse : [ADRESSE CLIENT]'
    )

    system_prompt = (
        "Tu es un AVOCAT EXPERT en droit immobilier tunisien (Cabinet KADASTRA & Associés).\n"
        f"{perm_prompt or ''}\n\n"
        "Ta mission est de rédiger un acte juridique d'une QUALITÉ IRRÉPROCHABLE, utilisant un français juridique "
        "formel, précis et rigoureux. Évite les répétitions et utilise les termes techniques appropriés (ex: preneur à bail, "
        "indemnité d'immobilisation, force probante, etc.).\n\n"
        "OBLIGATIONS DE STRUCTURE PROFESSIONNELLE :\n"
        "1. TITRE SOLENNEL en majuscules.\n"
        "2. EXPOSÉ DES MOTIFS : Une brève section expliquant l'intention des parties.\n"
        "3. DÉSIGNATION DES PARTIES : Utilise 'D'UNE PART' et 'D'AUTRE PART'.\n"
        "4. ARTICLES NUMÉROTÉS avec des titres explicites en gras.\n"
        "5. RÉFÉRENCES AU COC : Cite systématiquement les articles du Code des Obligations et des Contrats tunisien.\n"
        "6. CLAUSES DE JURIDICTION : Mentionne explicitement le Tribunal de Première Instance.\n"
        "7. FORMULE DE CLÔTURE : 'Fait à... en autant d'exemplaires que de parties...'.\n\n"
        f"{rag_context}\n\n"
        "IMPORTANT : Le contrat doit être exhaustif. Ne résume rien. Chaque clause doit être protégée juridiquement."
    )

    user_message = (
        f'Génère le contrat COMPLET : "{get_contract_title(contract_type, listing)}"\n\n'
        f'ANNONCE :\n{listing_info}\n\n'
        f'{vendeur_block}\n'
        f'{acheteur_block}\n\n'
        f'{nlp_section}\n\n'
        'STRUCTURE OBLIGATOIRE DU CONTRAT :\n'
        'Article 1 — Identification des parties (NOM, CIN, adresse complète)\n'
        'Article 2 — Désignation du bien (adresse, superficie, titre foncier)\n'
        'Article 3 — Prix et modalités de paiement (chiffres ET lettres, DT)\n'
        'Article 4 — Obligations du vendeur/bailleur (références COC)\n'
        'Article 5 — Obligations de l\'acquéreur/locataire (références COC)\n'
        'Article 6 — Garanties légales (éviction, vices cachés, Art. 641 COC)\n'
        'Article 7 — Conditions de résiliation et pénalités\n'
        'Article 8 — Enregistrement fiscal et frais (recette des finances)\n'
        'Article 9 — Juridiction compétente (Tribunal de Première Instance)\n'
        'Article 10 — Signatures, date et lieu\n\n'
        'Génère le contrat INTÉGRAL avec tous les articles ci-dessus, en citant les '
        'articles du COC et de la Loi 77-40 :'
    )

    return system_prompt, user_message, entities


def evaluate_contract_quality(contract_text, contract_type='vente'):
    """
    Combined KPI: 60% keyword match + 40% NLP score.
    Returns full evaluation dict.
    """
    c = contract_text.lower()
    clause_checks_def = CLAUSE_CHECKS.get(contract_type, CLAUSE_CHECKS['vente'])
    kw_results = {}
    for name, kws in clause_checks_def.items():
        kw_results[name] = any(k in c for k in kws)

    kw_score = sum(kw_results.values())
    kw_total = len(kw_results)

    # NLP score (NLP 7)
    nlp_rep = validate_contract_nlp(contract_text, contract_type)

    combined_ccr = round(
        (kw_score / kw_total * 0.6 + nlp_rep['ccr_nlp'] / 100 * 0.4) * 100, 1
    ) if kw_total > 0 else 0

    return {
        'clean_contract_rate': combined_ccr,
        'kw_ccr': round(kw_score / kw_total * 100, 1) if kw_total > 0 else 0,
        'nlp_ccr': nlp_rep['ccr_nlp'],
        'error_rate': round(100 - combined_ccr, 1),
        'clauses_found': kw_score,
        'clauses_total': kw_total,
        'missing_clauses': [n for n, f in kw_results.items() if not f],
        'nlp_obligations': len(nlp_rep['obligations_found']),
        'nlp_legal_refs': len(nlp_rep['legal_refs_found']),
        'is_clean': combined_ccr >= 80,
        'nlp_report': nlp_rep,
    }
