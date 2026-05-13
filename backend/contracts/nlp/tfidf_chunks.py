"""
NLP 4 — Noun chunks scored by legal TF-IDF.
Ranks noun phrases by juridical relevance using a domain-specific corpus.
"""
from sklearn.feature_extraction.text import TfidfVectorizer
from .config import LEGAL_CORPUS_REF, LEGAL_DICTIONARY_FR, LEGAL_NOUNS

# ── Lazy-loaded singleton ─────────────────────────────────────────────────────
_tfidf_vectorizer = None
_tfidf_vocab = None


def _get_tfidf():
    """Build and cache the TF-IDF vectorizer trained on legal corpus."""
    global _tfidf_vectorizer, _tfidf_vocab
    if _tfidf_vectorizer is not None:
        return _tfidf_vectorizer, _tfidf_vocab

    _tfidf_vectorizer = TfidfVectorizer(
        analyzer='word',
        ngram_range=(1, 3),
        min_df=1,
        max_features=500,
        sublinear_tf=True,
    )
    _tfidf_vectorizer.fit(LEGAL_CORPUS_REF)
    _tfidf_vocab = set(_tfidf_vectorizer.get_feature_names_out())
    return _tfidf_vectorizer, _tfidf_vocab


def score_noun_chunk(chunk_text):
    """
    Score a noun chunk for legal relevance.
    Combines: TF-IDF vocab presence + legal dictionary bonus + domain bonus.
    """
    _, tfidf_vocab = _get_tfidf()
    words = chunk_text.lower().split()
    if len(words) < 2:
        return 0.0

    # TF-IDF word scores
    tfidf_scores = [1.0 if word in tfidf_vocab else 0.0 for word in words]
    tfidf_score = sum(tfidf_scores) / len(words) if words else 0.0

    # Legal dictionary bonus
    legal_bonus = 0.3 if any(w in LEGAL_DICTIONARY_FR for w in words) else 0.0

    # Domain bonus (Tunisia / real estate)
    domain_terms = ['tunis', 'sfax', 'sousse', 'terrain', 'titre foncier',
                    'appartement', 'villa']
    domain_bonus = 0.2 if any(
        t in chunk_text.lower() for t in domain_terms
    ) else 0.0

    return round(min(1.0, tfidf_score + legal_bonus + domain_bonus), 3)


def extract_ranked_noun_chunks(doc, top_n=8, min_score=0.1):
    """
    Extract and rank noun chunks by legal relevance.
    Returns top_n chunks with their scores.
    """
    scored_chunks = []
    seen = set()

    for chunk in doc.noun_chunks:
        chunk_text = chunk.text.strip()
        root_lemma = chunk.root.lemma_.lower()

        if chunk_text.lower() in seen:
            continue
        if len(chunk_text.split()) < 2:
            continue

        score = score_noun_chunk(chunk_text)

        # Boost if root is a known legal noun
        if root_lemma in LEGAL_NOUNS:
            score = min(1.0, score + 0.25)

        if score >= min_score:
            scored_chunks.append({
                'text': chunk_text,
                'score': score,
                'root': root_lemma,
            })
            seen.add(chunk_text.lower())

    scored_chunks.sort(key=lambda x: x['score'], reverse=True)
    return scored_chunks[:top_n]
