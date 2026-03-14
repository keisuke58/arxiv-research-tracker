"""Semantic similarity scoring using sentence embeddings (no API required).

Uses sentence-transformers with a lightweight model (~22MB).
Falls back to keyword scoring if sentence-transformers is not installed.

Install: pip install sentence-transformers
"""

import math
from typing import Any

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_EMBEDDINGS = True
except ImportError:
    HAS_EMBEDDINGS = False


_model_cache = {}


def _get_model(model_name: str = "all-MiniLM-L6-v2") -> "SentenceTransformer":
    if model_name not in _model_cache:
        _model_cache[model_name] = SentenceTransformer(model_name)
    return _model_cache[model_name]


def score_by_embedding(
    papers: list[dict[str, Any]],
    interest: str,
    threshold: int = 6,
    model_name: str = "all-MiniLM-L6-v2",
) -> list[dict[str, Any]]:
    """Score papers using semantic similarity between interest and paper text.

    Uses cosine similarity between sentence embeddings of the interest
    description and each paper's title + abstract.
    """
    if not HAS_EMBEDDINGS:
        print("  sentence-transformers not installed, falling back to keyword scoring")
        from keyword_scorer import score_by_keywords
        return score_by_keywords(papers, interest, threshold=threshold)

    if not papers or not interest:
        return papers

    model = _get_model(model_name)

    # Encode interest description
    interest_emb = model.encode([interest], normalize_embeddings=True)[0]

    # Encode all papers (title + abstract)
    paper_texts = [
        f"{p.get('title', '')}. {p.get('abstract', '')}"
        for p in papers
    ]
    paper_embs = model.encode(paper_texts, normalize_embeddings=True, show_progress_bar=False)

    # Compute cosine similarities (already normalized, so just dot product)
    similarities = np.dot(paper_embs, interest_emb)

    # Normalize to 1-10 scale
    sim_min = float(similarities.min())
    sim_max = float(similarities.max())
    sim_range = sim_max - sim_min if sim_max > sim_min else 1.0

    for i, p in enumerate(papers):
        # Map similarity to 1-10
        normalized = (similarities[i] - sim_min) / sim_range
        score = int(round(normalized * 9)) + 1
        p["relevance_score"] = score

        # Generate reason based on similarity
        sim_pct = int(similarities[i] * 100)
        p["relevance_reason"] = f"Semantic similarity: {sim_pct}%"

    # Sort by score descending
    papers.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    above = sum(1 for p in papers if p.get("relevance_score", 0) >= threshold)
    print(f"  {above} papers above threshold ({threshold}), {len(papers) - above} below")

    return papers
