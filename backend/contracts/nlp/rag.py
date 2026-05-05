"""
NLP 6 — RAG vectoriel: sentence-transformers + FAISS.
Semantic search over Tunisian legal knowledge base.
"""
import numpy as np
from .config import LEGAL_CHUNKS

# ── Lazy-loaded singletons ────────────────────────────────────────────────────
_embedder = None
_faiss_index = None


def _get_embedder():
    """Load the sentence-transformers model (cached)."""
    global _embedder
    if _embedder is not None:
        return _embedder
    from sentence_transformers import SentenceTransformer
    _embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _embedder


def _get_faiss_index():
    """Build the FAISS index over legal chunks (cached)."""
    global _faiss_index
    if _faiss_index is not None:
        return _faiss_index

    import faiss
    embedder = _get_embedder()
    chunk_texts = [c['text'] for c in LEGAL_CHUNKS]
    embeddings = embedder.encode(chunk_texts, show_progress_bar=False)
    embeddings = np.array(embeddings, dtype='float32')

    # L2 normalize for cosine similarity via dot product
    faiss.normalize_L2(embeddings)

    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)
    _faiss_index = index
    return index


def semantic_legal_search(query, contract_type=None, top_k=4):
    """
    Semantic search in the Tunisian legal knowledge base.
    Returns top_k most relevant chunks for the query.
    """
    import faiss
    embedder = _get_embedder()
    index = _get_faiss_index()

    query_vec = embedder.encode([query], show_progress_bar=False)
    query_vec = np.array(query_vec, dtype='float32')
    faiss.normalize_L2(query_vec)

    scores, indices = index.search(query_vec, top_k * 2)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        chunk = LEGAL_CHUNKS[idx]
        # Optional filter by contract type
        if contract_type and chunk['type'] not in (contract_type, 'general'):
            continue
        results.append({**chunk, 'similarity': round(float(score), 4)})
        if len(results) >= top_k:
            break
    return results


def build_rag_context(query, contract_type, top_k=4):
    """Build the RAG context string for the LLM prompt."""
    chunks = semantic_legal_search(query, contract_type, top_k)
    if not chunks:
        return ''
    context_lines = ['RÉFÉRENCES LÉGALES (RAG sémantique) :']
    for c in chunks:
        context_lines.append(
            f'[{c["article"]} | sim={c["similarity"]:.2f}] {c["text"]}'
        )
    return '\n'.join(context_lines)
