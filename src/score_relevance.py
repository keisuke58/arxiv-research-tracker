"""Score paper relevance using LLM."""

import json
import os
from typing import Any

from openai import OpenAI


SCORING_PROMPT = """\
You are a research paper relevance scorer. Given a researcher's interests and a batch of arXiv paper abstracts, rate each paper's relevance on a scale of 1-10.

Output one JSON object per paper, in the same order as input. Each object must have:
- "score": integer 1-10 (10 = extremely relevant)
- "reason": 1-2 sentence explanation of why the paper is or isn't relevant

Rules:
- Be strict: only give 8+ to papers that directly address the stated interests
- A score of 5-7 means tangentially related
- A score of 1-4 means not relevant
- Respond ONLY with a JSON array, no other text

Research interests:
{interest}

Papers:
{papers}
"""


def _build_paper_text(papers: list[dict], start_idx: int = 0) -> str:
    lines = []
    for i, p in enumerate(papers, start=start_idx + 1):
        lines.append(f"{i}. Title: {p['title']}")
        lines.append(f"   Authors: {', '.join(p['authors'][:5])}")
        lines.append(f"   Abstract: {p['abstract'][:500]}")
        lines.append("")
    return "\n".join(lines)


def _create_client(config: dict) -> OpenAI:
    """Create OpenAI-compatible client from config."""
    provider = config.get("provider", "openai")
    base_url = config.get("base_url")

    if provider == "deepseek" and not base_url:
        base_url = "https://api.deepseek.com"

    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")

    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    return OpenAI(**kwargs)


def score_papers(
    papers: list[dict[str, Any]],
    interest: str,
    llm_config: dict,
    batch_size: int = 8,
    threshold: int = 6,
) -> list[dict[str, Any]]:
    """Score papers for relevance using LLM.

    Returns papers with added 'relevance_score' and 'relevance_reason' fields,
    sorted by score descending.
    """
    if not papers:
        return []

    client = _create_client(llm_config)
    model = llm_config.get("model", "deepseek-chat")
    temperature = llm_config.get("scoring_temperature", 0.3)

    scored = []

    for batch_start in range(0, len(papers), batch_size):
        batch = papers[batch_start : batch_start + batch_size]
        paper_text = _build_paper_text(batch, start_idx=batch_start)

        prompt = SCORING_PROMPT.format(interest=interest, papers=paper_text)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=256 * len(batch),
            )
            content = response.choices[0].message.content.strip()

            # Parse JSON array from response
            # Handle cases where LLM wraps in ```json ... ```
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            scores = json.loads(content)

            for i, paper in enumerate(batch):
                if i < len(scores):
                    paper["relevance_score"] = int(scores[i].get("score", 0))
                    paper["relevance_reason"] = scores[i].get("reason", "")
                else:
                    paper["relevance_score"] = 0
                    paper["relevance_reason"] = "LLM did not return score"
                scored.append(paper)

        except Exception as e:
            print(f"  Scoring error for batch {batch_start}: {e}")
            for paper in batch:
                paper["relevance_score"] = 0
                paper["relevance_reason"] = f"Scoring failed: {e}"
                scored.append(paper)

        batch_idx = batch_start // batch_size + 1
        total_batches = (len(papers) + batch_size - 1) // batch_size
        print(f"  Scored batch {batch_idx}/{total_batches}")

    # Sort by score descending
    scored.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    # Filter by threshold
    above = [p for p in scored if p.get("relevance_score", 0) >= threshold]
    below = [p for p in scored if p.get("relevance_score", 0) < threshold]

    print(f"  {len(above)} papers above threshold ({threshold}), {len(below)} below")
    return scored
