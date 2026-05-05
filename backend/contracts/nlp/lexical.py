"""
NLP 2 — Lemmatisation + RapidFuzz synonym expansion.
Transforms everyday language into formal legal terminology.
"""
from rapidfuzz import fuzz, process as rfprocess
from .config import LEGAL_DICTIONARY_FR

LEGAL_KEYS = list(LEGAL_DICTIONARY_FR.keys())


def fuzzy_legal_lookup(word, threshold=82):
    """
    Find the legal term matching `word` via fuzzy string matching.
    Returns (legal_term, score) or (None, 0).
    """
    word_lower = word.lower()
    # Exact match first
    if word_lower in LEGAL_DICTIONARY_FR:
        return LEGAL_DICTIONARY_FR[word_lower], 100
    # Fuzzy match on keys
    best_match = rfprocess.extractOne(
        word_lower, LEGAL_KEYS,
        scorer=fuzz.ratio,
        score_cutoff=threshold
    )
    if best_match:
        matched_key, score, _ = best_match
        return LEGAL_DICTIONARY_FR[matched_key], score
    return None, 0


def transform_to_legal_terms_advanced(text):
    """
    Advanced lexical transformation:
    1. spaCy segmentation (doc.sents)
    2. Token-by-token lemmatization
    3. Exact lookup in legal dictionary
    4. Fuzzy fallback for spelling variants
    5. Preserve original casing
    
    Returns (transformed_text, replacements_log).
    """
    from .ner import get_nlp
    nlp = get_nlp()
    doc = nlp(text)
    result_sentences = []
    replacements_log = []

    for sent in doc.sents:
        tokens_out = []
        for token in sent:
            if token.is_space or token.is_punct:
                tokens_out.append(token.text)
                continue

            lemma = token.lemma_.lower()
            orig = token.text

            # 1. Exact lookup on lemma
            legal_exact = LEGAL_DICTIONARY_FR.get(lemma)
            if legal_exact:
                tokens_out.append(legal_exact)
                replacements_log.append((orig, legal_exact, 'exact', 100))
                continue

            # 2. Exact lookup on raw text
            legal_raw = LEGAL_DICTIONARY_FR.get(orig.lower())
            if legal_raw:
                tokens_out.append(legal_raw)
                replacements_log.append((orig, legal_raw, 'exact_raw', 100))
                continue

            # 3. Fuzzy fallback (only for words >= 5 chars, not stopwords)
            if not token.is_stop and len(orig) >= 5:
                legal_fuzzy, score = fuzzy_legal_lookup(lemma)
                if legal_fuzzy and score >= 85:
                    tokens_out.append(legal_fuzzy)
                    replacements_log.append((orig, legal_fuzzy, 'fuzzy', score))
                    continue

            tokens_out.append(orig)

        sentence = ' '.join(tokens_out).strip()
        if sentence:
            result_sentences.append(sentence.capitalize())

    return ' '.join(result_sentences), replacements_log
