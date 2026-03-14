"""Composite 100-point paper quality scorer (no LLM required).

Strict, quantitative evaluation. Most papers score 30-50 (grade C/D).
Only genuinely strong papers reach 70+ (grade A/S).

Dimensions:
  - Relevance to interests     (0-25)  scaled from keyword/embedding score
  - Quantitative evidence       (0-25)  actual numbers, benchmarks, baselines
  - Code & reproducibility      (0-20)  code link, stars, datasets, ablations
  - Novelty signals             (0-15)  "first", "novel", but penalize vague hype
  - Scale & rigor               (0-15)  authors, cross-disciplinary, thoroughness
"""

import re
from typing import Any


# --- Quantitative evidence patterns ---
# Matches: "3.2% improvement", "improves by 5pp", "2.1x faster", "reduces ... by 15%"
PAT_PERCENT_GAIN = re.compile(
    r"(\d+\.?\d*)\s*(%|percent|pp|percentage\s*point)\s+"
    r"(improvement|better|gain|increase|reduction|decrease|higher|lower|drop)",
    re.IGNORECASE,
)
PAT_SPEEDUP = re.compile(
    r"(\d+\.?\d*)\s*[x×]\s*(faster|speedup|speed-up|acceleration)",
    re.IGNORECASE,
)
PAT_ABSOLUTE_RESULT = re.compile(
    r"(accuracy|precision|recall|f1|auc|bleu|rouge|map|miou|psnr|ssim|fid|is|lpips)"
    r"\s*(of|=|:|\s)\s*(\d+\.?\d*)",
    re.IGNORECASE,
)
PAT_DATASET_SIZE = re.compile(
    r"(\d[\d,]*)\s*(samples|images|examples|instances|data\s*points|patients|subjects|sentences|tokens|hours)",
    re.IGNORECASE,
)
PAT_COMPARISON_COUNT = re.compile(
    r"compar\w+\s+(with|to|against)\s+(\d+)\s+(method|baseline|approach|model)",
    re.IGNORECASE,
)

# --- Novelty / hype detection ---
NOVELTY_GENUINE = [
    "first to", "first time", "for the first time", "we introduce",
    "we propose a new", "novel framework", "novel method",
    "new paradigm", "new approach",
]
HYPE_VAGUE = [
    "revolutionary", "groundbreaking", "game-changing", "unprecedented",
    "remarkable", "dramatically", "vastly superior",
]

# --- Reproducibility keywords ---
REPRO_STRONG = [
    "ablation study", "ablation experiment", "open-source", "publicly available",
    "code available", "our code", "github.com", "reproducib",
]
REPRO_MODERATE = [
    "benchmark", "baseline comparison", "evaluation protocol",
    "cross-validation", "held-out", "test set", "validation set",
]


def compute_quality_score(paper: dict[str, Any], relevance_score: int = 0) -> dict[str, Any]:
    """Compute a strict 100-point quality score.

    Most papers will score 30-50. Only genuinely strong papers reach 70+.
    """
    text = " ".join([
        paper.get("title", ""),
        paper.get("abstract", ""),
        paper.get("comment", ""),
    ]).lower()

    # --- 1. Relevance (0-25) ---
    # Non-linear: score 10 → 25pts, score 7 → 15pts, score 5 → 8pts
    rel = max(0, min(relevance_score, 10))
    if rel >= 9:
        relevance_pts = 25
    elif rel >= 7:
        relevance_pts = 12 + (rel - 7) * 4  # 12, 16, 20
    elif rel >= 5:
        relevance_pts = 5 + (rel - 5) * 3   # 5, 8, 11
    else:
        relevance_pts = max(0, rel - 1)      # 0,0,1,2,3

    # --- 2. Quantitative evidence (0-25) ---
    quant_pts = _score_quantitative(text)

    # --- 3. Code & reproducibility (0-20) ---
    code_repro_pts = _score_code_repro(paper, text)

    # --- 4. Novelty (0-15) ---
    novelty_pts = _score_novelty(text)

    # --- 5. Scale & rigor (0-15) ---
    rigor_pts = _score_rigor(paper, text)

    total = relevance_pts + quant_pts + code_repro_pts + novelty_pts + rigor_pts
    total = min(total, 100)

    grade = _grade(total)

    return {
        "quality_score": total,
        "quality_breakdown": {
            "relevance": relevance_pts,
            "quantitative": quant_pts,
            "code_repro": code_repro_pts,
            "novelty": novelty_pts,
            "rigor": rigor_pts,
        },
        "quality_grade": grade,
    }


def _score_quantitative(text: str) -> int:
    """Score quantitative evidence (0-25). This is the hardest to earn."""
    pts = 0

    # Percentage improvements with context
    pct_matches = PAT_PERCENT_GAIN.findall(text)
    for match in pct_matches:
        val = float(match[0])
        if val >= 10:
            pts += 5  # Big improvement
        elif val >= 3:
            pts += 3
        elif val >= 1:
            pts += 2
    pts = min(pts, 10)  # Cap at 10 from percentages

    # Speedup claims
    speed_matches = PAT_SPEEDUP.findall(text)
    for match in speed_matches:
        val = float(match[0])
        if val >= 10:
            pts += 4
        elif val >= 2:
            pts += 3
        else:
            pts += 1
    pts = min(pts, 13)

    # Absolute metric values (shows they actually measured)
    abs_matches = PAT_ABSOLUTE_RESULT.findall(text)
    pts += min(len(abs_matches) * 2, 6)

    # Number of baseline comparisons mentioned
    comp_matches = PAT_COMPARISON_COUNT.findall(text)
    if comp_matches:
        n_compared = max(int(m[1]) for m in comp_matches)
        if n_compared >= 10:
            pts += 4
        elif n_compared >= 5:
            pts += 3
        elif n_compared >= 3:
            pts += 2

    # Dataset size mentioned (shows real experiments)
    ds_matches = PAT_DATASET_SIZE.findall(text)
    if ds_matches:
        pts += 2

    return min(pts, 25)


def _score_code_repro(paper: dict, text: str) -> int:
    """Score code availability + reproducibility signals (0-20)."""
    pts = 0

    # Code availability (0-10)
    code = paper.get("code")
    if code:
        pts += 4  # Has code link
        stars = code.get("stars", 0)
        if stars >= 500:
            pts += 6
        elif stars >= 100:
            pts += 5
        elif stars >= 50:
            pts += 4
        elif stars >= 10:
            pts += 2
        elif stars > 0:
            pts += 1
    elif any(kw in text for kw in ["code available", "github.com", "our code"]):
        pts += 2  # Mentions code but we didn't detect URL

    # Reproducibility signals (0-10)
    strong = sum(1 for kw in REPRO_STRONG if kw in text)
    pts += min(strong * 3, 6)

    moderate = sum(1 for kw in REPRO_MODERATE if kw in text)
    pts += min(moderate * 1, 4)

    return min(pts, 20)


def _score_novelty(text: str) -> int:
    """Score novelty signals (0-15). Penalizes vague hype."""
    pts = 0

    # Genuine novelty claims
    genuine = sum(1 for kw in NOVELTY_GENUINE if kw in text)
    pts += min(genuine * 3, 9)

    # Theoretical contribution signals
    theory_kws = ["theorem", "proof", "lemma", "convergence guarantee", "bound"]
    theory = sum(1 for kw in theory_kws if kw in text)
    pts += min(theory * 3, 6)

    # Penalty for vague hype without substance
    hype = sum(1 for kw in HYPE_VAGUE if kw in text)
    if hype > 0 and pts < 5:
        pts = max(0, pts - hype * 2)

    return min(pts, 15)


def _score_rigor(paper: dict, text: str) -> int:
    """Score scale & rigor (0-15)."""
    pts = 0

    # Author count (larger team = usually more thorough)
    authors = paper.get("authors", [])
    n = len(authors)
    if n >= 15:
        pts += 5
    elif n >= 8:
        pts += 4
    elif n >= 4:
        pts += 3
    elif n >= 2:
        pts += 2
    else:
        pts += 1

    # Cross-disciplinary (multiple arXiv categories)
    cats = paper.get("categories", [])
    if len(cats) >= 4:
        pts += 3
    elif len(cats) >= 2:
        pts += 1

    # Thoroughness signals
    thorough_kws = [
        "supplementary", "appendix", "detailed analysis",
        "statistical significance", "confidence interval",
        "error bar", "standard deviation", "p-value",
        "hyperparameter", "sensitivity analysis",
    ]
    thorough = sum(1 for kw in thorough_kws if kw in text)
    pts += min(thorough * 2, 7)

    return min(pts, 15)


def _grade(score: int) -> str:
    """Strict grading. Most papers are C or D."""
    if score >= 80:
        return "S"
    if score >= 65:
        return "A"
    if score >= 50:
        return "B"
    if score >= 35:
        return "C"
    return "D"


def apply_quality_scores(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply quality scoring to a list of papers (in-place).

    Assumes relevance_score is already set on each paper.
    Sorts by quality_score descending.
    """
    for p in papers:
        rel = p.get("relevance_score", 0)
        result = compute_quality_score(p, relevance_score=rel)
        p["quality_score"] = result["quality_score"]
        p["quality_breakdown"] = result["quality_breakdown"]
        p["quality_grade"] = result["quality_grade"]

    papers.sort(key=lambda x: x.get("quality_score", 0), reverse=True)
    return papers
