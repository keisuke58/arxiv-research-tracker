"""Keyword-based relevance scoring (no LLM required).

Fast, free alternative to LLM scoring. Uses TF-IDF-like keyword matching
between the user's interest description and paper title+abstract.
"""

import math
import re
from collections import Counter
from typing import Any


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, split on non-alphanumeric, remove short tokens."""
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    return [t for t in tokens if len(t) > 2]


def _extract_phrases(text: str) -> list[str]:
    """Extract multi-word phrases (bigrams) for better matching."""
    tokens = _tokenize(text)
    phrases = list(tokens)
    for i in range(len(tokens) - 1):
        phrases.append(f"{tokens[i]} {tokens[i+1]}")
    return phrases


def _compute_idf(docs: list[list[str]]) -> dict[str, float]:
    """Compute inverse document frequency."""
    n = len(docs)
    if n == 0:
        return {}
    df = Counter()
    for doc_tokens in docs:
        unique = set(doc_tokens)
        for token in unique:
            df[token] += 1
    return {token: math.log(n / (count + 1)) + 1 for token, count in df.items()}


def score_by_keywords(
    papers: list[dict[str, Any]],
    interest: str,
    threshold: int = 6,
) -> list[dict[str, Any]]:
    """Score papers using keyword matching against interest description.

    Scoring method:
    - Tokenize interest and each paper's title+abstract
    - Compute cosine similarity with IDF weighting
    - Normalize to 1-10 scale
    """
    if not papers or not interest:
        return papers

    interest_tokens = _extract_phrases(interest)
    interest_set = set(interest_tokens)
    interest_counter = Counter(interest_tokens)

    # Tokenize all papers
    paper_tokens = []
    for p in papers:
        text = f"{p.get('title', '')} {p.get('abstract', '')}"
        tokens = _extract_phrases(text)
        paper_tokens.append(tokens)

    # Compute IDF across all papers
    idf = _compute_idf(paper_tokens)

    # Score each paper
    raw_scores = []
    for i, tokens in enumerate(paper_tokens):
        doc_counter = Counter(tokens)
        # Weighted overlap with interest
        score = 0.0
        norm_interest = 0.0
        norm_doc = 0.0

        all_terms = interest_set | set(tokens)
        for term in all_terms:
            w = idf.get(term, 1.0)
            a = interest_counter.get(term, 0) * w
            b = doc_counter.get(term, 0) * w
            score += a * b
            norm_interest += a * a
            norm_doc += b * b

        # Cosine similarity
        denom = math.sqrt(norm_interest) * math.sqrt(norm_doc)
        cosine = score / denom if denom > 0 else 0.0
        raw_scores.append(cosine)

    # Normalize to 1-10 scale
    if raw_scores:
        max_score = max(raw_scores) if max(raw_scores) > 0 else 1.0
        for i, p in enumerate(papers):
            normalized = int(round(raw_scores[i] / max_score * 9)) + 1  # 1-10
            p["relevance_score"] = normalized
            # Generate simple reason
            common = interest_set & set(paper_tokens[i])
            top_matches = sorted(common, key=lambda t: len(t), reverse=True)[:5]
            if top_matches:
                p["relevance_reason"] = f"Keyword matches: {', '.join(top_matches)}"
            else:
                p["relevance_reason"] = "Low keyword overlap with interests"

    # Sort by score descending
    papers.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    above = sum(1 for p in papers if p.get("relevance_score", 0) >= threshold)
    print(f"  {above} papers above threshold ({threshold}), {len(papers) - above} below")

    return papers
