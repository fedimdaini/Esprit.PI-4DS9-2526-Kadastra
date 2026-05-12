"""
NLP 1 — NER spaCy + EntityRuler for Tunisian real estate domain.
Loads fr_core_news_lg (or sm fallback) and adds custom entity patterns.
"""
import spacy
from spacy.pipeline import EntityRuler
from .config import TUNISIAN_LOCATIONS, RE_PROPERTY_TYPES, LEGAL_DOCS

# ── Lazy-loaded singleton ─────────────────────────────────────────────────────
_nlp_instance = None


def get_nlp():
    """Get or create the spaCy NLP pipeline with custom EntityRuler."""
    global _nlp_instance
    if _nlp_instance is not None:
        return _nlp_instance

    try:
        nlp = spacy.load('fr_core_news_lg')
    except OSError:
        try:
            nlp = spacy.load('fr_core_news_sm')
        except OSError:
            raise RuntimeError(
                "No French spaCy model found. Install with: "
                "python -m spacy download fr_core_news_lg"
            )

    # Remove existing ruler if present (safe for re-init)
    if 'kadastra_ruler' in nlp.pipe_names:
        nlp.remove_pipe('kadastra_ruler')

    ruler = nlp.add_pipe('entity_ruler', name='kadastra_ruler', before='ner')

    patterns = []
    # Locations
    for loc in TUNISIAN_LOCATIONS:
        patterns.append({'label': 'LOC', 'pattern': loc})
        patterns.append({'label': 'LOC', 'pattern': loc.lower()})
    # Property types
    for prop in RE_PROPERTY_TYPES:
        patterns.append({'label': 'PROPERTY', 'pattern': prop})
        patterns.append({'label': 'PROPERTY', 'pattern': [
            {'LOWER': w.lower()} for w in prop.split()
        ]})
    # Legal documents
    for doc in LEGAL_DOCS:
        patterns.append({'label': 'LEGAL_DOC', 'pattern': doc})
        patterns.append({'label': 'LEGAL_DOC', 'pattern': [
            {'LOWER': w.lower()} for w in doc.split()
        ]})

    ruler.add_patterns(patterns)
    _nlp_instance = nlp
    return nlp


def extract_entities_advanced(listing):
    """
    NER extraction with POS-based filtering.
    Returns dict with lieux, dates, montants, personnes, organisations,
    biens, docs_legaux, lemmes_cles, verbes_cles, obligations.
    """
    from .pos_obligations import extract_obligations_from_text

    nlp = get_nlp()

    text_fields = [
        str(listing.get('titre', '') or ''),
        str(listing.get('description', '') or ''),
        str(listing.get('localisation', '') or ''),
        str(listing.get('adresse', '') or ''),
    ]
    full_text = ' '.join([t for t in text_fields if t.strip()])
    doc = nlp(full_text)

    entities = {
        'lieux': [],
        'dates': [],
        'montants': [],
        'personnes': [],
        'organisations': [],
        'biens': [],
        'docs_legaux': [],
        'lemmes_cles': [],
        'verbes_cles': [],
        'obligations': [],
    }

    for ent in doc.ents:
        raw = ent.text.strip()
        lemma = ent.lemma_.strip()
        if not raw:
            continue

        # POS-based filtering (NLP 3 integration)
        pos_ok = True
        if ent.label_ in ('LOC', 'GPE') and ent.root.pos_ not in ('PROPN', 'NOUN'):
            pos_ok = False
        if ent.label_ == 'PER' and ent.root.pos_ != 'PROPN':
            pos_ok = False
        if not pos_ok:
            continue

        if ent.label_ in ('LOC', 'GPE', 'LOCATION'):
            entities['lieux'].append(lemma or raw)
        elif ent.label_ in ('DATE', 'TIME'):
            entities['dates'].append(raw)
        elif ent.label_ in ('MONEY', 'CARDINAL', 'QUANTITY'):
            entities['montants'].append(raw)
        elif ent.label_ in ('PER', 'PERSON'):
            entities['personnes'].append(raw)
        elif ent.label_ == 'ORG':
            entities['organisations'].append(raw)
        elif ent.label_ == 'PROPERTY':
            entities['biens'].append(raw)
        elif ent.label_ == 'LEGAL_DOC':
            entities['docs_legaux'].append(raw)

    # Obligations (NLP 3)
    entities['obligations'] = extract_obligations_from_text(full_text)

    # Key verbs
    seen_verbs = set()
    for token in doc:
        if (token.pos_ == 'VERB' and not token.is_stop
                and token.dep_ not in ('aux', 'aux:pass')):
            lemma_v = token.lemma_.lower()
            if lemma_v not in seen_verbs and len(lemma_v) > 3:
                entities['verbes_cles'].append(lemma_v)
                seen_verbs.add(lemma_v)

    # Key lemmas
    seen_lemmas = set()
    for token in doc:
        if (token.pos_ in ('NOUN', 'PROPN') and not token.is_stop
                and len(token.text) > 3):
            lemma = token.lemma_.lower()
            if lemma not in seen_lemmas:
                entities['lemmes_cles'].append(lemma)
                seen_lemmas.add(lemma)

    # Deduplicate (skip obligations — contains dicts)
    for key in entities:
        if isinstance(entities[key], list) and key != 'obligations':
            entities[key] = list(dict.fromkeys(entities[key]))

    return entities
