"""Generate structured summaries using LLM."""

import json
import os
from typing import Any

from openai import OpenAI


SUMMARY_PROMPT = """\
You are a research paper analyst. For each paper below, generate a structured summary.

Output a JSON array with one object per paper, in order. Each object must have:
- "tldr": 1-2 sentence "too long; didn't read" summary
- "motivation": Why this research was done (1-2 sentences)
- "method": Key methodology (1-2 sentences)
- "result": Main results/findings (1-2 sentences)
- "conclusion": Takeaway and implications (1 sentence)

Respond ONLY with the JSON array, no other text.
Language: {language}

Papers:
{papers}
"""


def _create_client(config: dict) -> OpenAI:
    provider = config.get("provider", "openai")
    base_url = config.get("base_url")
    if provider == "deepseek" and not base_url:
        base_url = "https://api.deepseek.com"
    api_key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _build_paper_text(papers: list[dict]) -> str:
    lines = []
    for i, p in enumerate(papers, 1):
        lines.append(f"{i}. Title: {p['title']}")
        lines.append(f"   Abstract: {p['abstract'][:600]}")
        lines.append("")
    return "\n".join(lines)


def summarize_papers(
    papers: list[dict[str, Any]],
    llm_config: dict,
    language: str = "English",
    batch_size: int = 4,
) -> list[dict[str, Any]]:
    """Add structured summaries to papers.

    Only summarizes papers that have relevance_score >= threshold (or all if no score).
    """
    if not papers:
        return papers

    client = _create_client(llm_config)
    model = llm_config.get("model", "deepseek-chat")
    temperature = llm_config.get("summary_temperature", 0.5)

    for batch_start in range(0, len(papers), batch_size):
        batch = papers[batch_start : batch_start + batch_size]
        paper_text = _build_paper_text(batch)

        prompt = SUMMARY_PROMPT.format(language=language, papers=paper_text)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=512 * len(batch),
            )
            content = response.choices[0].message.content.strip()

            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0]
            summaries = json.loads(content)

            for i, paper in enumerate(batch):
                if i < len(summaries):
                    paper["summary"] = summaries[i]
                else:
                    paper["summary"] = _default_summary()

        except Exception as e:
            print(f"  Summary error for batch {batch_start}: {e}")
            for paper in batch:
                paper["summary"] = _default_summary()

        batch_idx = batch_start // batch_size + 1
        total_batches = (len(papers) + batch_size - 1) // batch_size
        print(f"  Summarized batch {batch_idx}/{total_batches}")

    return papers


def _default_summary() -> dict:
    return {
        "tldr": "Summary generation failed",
        "motivation": "N/A",
        "method": "N/A",
        "result": "N/A",
        "conclusion": "N/A",
    }
