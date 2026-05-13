"""
NLP 3 — POS tagging for obligation extraction and NER filtering.
Extracts legal obligation verbs (doit, est tenu, s'engage, interdit...).
"""
from .config import OBLIGATION_PATTERNS


def extract_obligations_from_text(text):
    """
    Extract legal obligations from text using POS + dependency parsing.
    Returns list of dicts: {type, pattern, clause, subject}.
    """
    from .ner import get_nlp
    nlp = get_nlp()
    doc = nlp(text)
    obligations = []

    for sent in doc.sents:
        sent_text_lower = sent.text.lower()
        for ob_type, patterns_list in OBLIGATION_PATTERNS.items():
            for pat in patterns_list:
                if pat in sent_text_lower:
                    # Find the grammatical subject via dependency parsing
                    subject = None
                    for token in sent:
                        if (token.dep_ in ('nsubj', 'nsubj:pass')
                                and token.pos_ in ('NOUN', 'PROPN', 'PRON')):
                            subject = token.lemma_
                            break
                    obligations.append({
                        'type': ob_type,
                        'pattern': pat,
                        'clause': sent.text.strip()[:120],
                        'subject': subject or 'inconnu'
                    })
                    break  # One match per sentence per type

    return obligations
