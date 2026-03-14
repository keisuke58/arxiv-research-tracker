"""Generate Markdown and HTML output from scored papers."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def generate_markdown(
    papers_by_profile: dict[str, list[dict[str, Any]]],
    date_str: str | None = None,
    threshold: int = 6,
) -> str:
    """Generate a Markdown digest for the given papers."""
    if date_str is None:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    lines = [f"# arXiv Digest — {date_str}", ""]

    total = sum(len(ps) for ps in papers_by_profile.values())
    relevant = sum(
        1 for ps in papers_by_profile.values()
        for p in ps if p.get("relevance_score", 0) >= threshold
    )
    lines.append(f"**{relevant} relevant papers** out of {total} total\n")

    for profile_name, papers in papers_by_profile.items():
        above = [p for p in papers if p.get("relevance_score", 0) >= threshold]
        if not above:
            continue

        lines.append(f"## {profile_name}")
        lines.append("")

        for p in above:
            score = p.get("relevance_score", "?")
            lines.append(f"### [{p['title']}]({p['abs_url']}) (Score: {score}/10)")
            lines.append("")

            # Authors
            authors = p.get("authors", [])
            if len(authors) > 5:
                author_str = ", ".join(authors[:5]) + f" et al. ({len(authors)} authors)"
            else:
                author_str = ", ".join(authors)
            lines.append(f"**Authors:** {author_str}")
            lines.append("")

            # Categories
            cats = ", ".join(p.get("categories", []))
            lines.append(f"**Categories:** `{cats}`")
            lines.append("")

            # Relevance reason
            reason = p.get("relevance_reason", "")
            if reason:
                lines.append(f"**Why relevant:** {reason}")
                lines.append("")

            # Summary
            summary = p.get("summary")
            if summary and isinstance(summary, dict):
                tldr = summary.get("tldr", "")
                if tldr:
                    lines.append(f"> **TL;DR:** {tldr}")
                    lines.append("")
                method = summary.get("method", "")
                if method and method != "N/A":
                    lines.append(f"**Method:** {method}")
                    lines.append("")
                result = summary.get("result", "")
                if result and result != "N/A":
                    lines.append(f"**Result:** {result}")
                    lines.append("")

            # Code link
            code = p.get("code")
            if code:
                code_str = f"[{code['url']}]({code['url']})"
                stars = code.get("stars")
                if stars is not None:
                    code_str += f" ({stars} stars)"
                lines.append(f"**Code:** {code_str}")
                lines.append("")

            lines.append(f"[PDF]({p.get('pdf_url', '')}) | [Abstract]({p['abs_url']})")
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines)


def generate_html(
    papers_by_profile: dict[str, list[dict[str, Any]]],
    date_str: str | None = None,
    threshold: int = 6,
) -> str:
    """Generate an HTML digest page."""
    if date_str is None:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    total = sum(len(ps) for ps in papers_by_profile.values())
    relevant = sum(
        1 for ps in papers_by_profile.values()
        for p in ps if p.get("relevance_score", 0) >= threshold
    )

    # Build profile sections
    sections_html = []
    for profile_name, papers in papers_by_profile.items():
        above = [p for p in papers if p.get("relevance_score", 0) >= threshold]
        if not above:
            continue
        cards = []
        for p in above:
            cards.append(_paper_card_html(p))
        section = f"""
    <section class="profile-section">
      <h2>{_esc(profile_name)} <span class="badge">{len(above)}</span></h2>
      {''.join(cards)}
    </section>"""
        sections_html.append(section)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>arXiv Digest — {date_str}</title>
  <style>
    :root {{
      --bg: #0d1117; --surface: #161b22; --border: #30363d;
      --text: #c9d1d9; --text-muted: #8b949e; --accent: #58a6ff;
      --green: #3fb950; --orange: #d29922; --red: #f85149;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
      background: var(--bg); color: var(--text); line-height: 1.6;
      max-width: 900px; margin: 0 auto; padding: 20px;
    }}
    h1 {{ color: var(--accent); margin-bottom: 8px; }}
    .stats {{ color: var(--text-muted); margin-bottom: 24px; font-size: 14px; }}
    h2 {{ color: var(--text); margin: 24px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 8px; }}
    .badge {{
      background: var(--accent); color: #000; border-radius: 12px;
      padding: 2px 10px; font-size: 13px; font-weight: 600;
    }}
    .paper-card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; padding: 16px; margin-bottom: 12px;
    }}
    .paper-card:hover {{ border-color: var(--accent); }}
    .paper-title {{ font-size: 16px; font-weight: 600; margin-bottom: 6px; }}
    .paper-title a {{ color: var(--accent); text-decoration: none; }}
    .paper-title a:hover {{ text-decoration: underline; }}
    .score {{
      display: inline-block; padding: 2px 8px; border-radius: 4px;
      font-size: 12px; font-weight: 700; margin-left: 8px;
    }}
    .score-high {{ background: var(--green); color: #000; }}
    .score-mid {{ background: var(--orange); color: #000; }}
    .score-low {{ background: var(--text-muted); color: #000; }}
    .meta {{ font-size: 13px; color: var(--text-muted); margin-bottom: 8px; }}
    .tldr {{ font-style: italic; margin: 8px 0; padding: 8px 12px;
             border-left: 3px solid var(--accent); background: rgba(88,166,255,0.05); }}
    .reason {{ font-size: 13px; color: var(--text-muted); margin-top: 6px; }}
    .links {{ margin-top: 8px; font-size: 13px; }}
    .links a {{ color: var(--accent); margin-right: 12px; text-decoration: none; }}
    .links a:hover {{ text-decoration: underline; }}
    .code-badge {{
      display: inline-block; background: var(--green); color: #000;
      padding: 1px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;
    }}
    .filter-bar {{
      margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap;
    }}
    .filter-bar input {{
      flex: 1; min-width: 200px; padding: 8px 12px; border-radius: 6px;
      border: 1px solid var(--border); background: var(--surface);
      color: var(--text); font-size: 14px;
    }}
    .filter-bar input:focus {{ outline: none; border-color: var(--accent); }}
    @media (max-width: 600px) {{
      body {{ padding: 12px; }}
      .paper-card {{ padding: 12px; }}
    }}
  </style>
</head>
<body>
  <h1>arXiv Digest</h1>
  <p class="stats">{date_str} &middot; {relevant} relevant / {total} total papers</p>

  <div class="filter-bar">
    <input type="text" id="search" placeholder="Filter papers..." oninput="filterPapers()">
  </div>

  {''.join(sections_html)}

  <script>
    function filterPapers() {{
      const q = document.getElementById('search').value.toLowerCase();
      document.querySelectorAll('.paper-card').forEach(card => {{
        card.style.display = card.textContent.toLowerCase().includes(q) ? '' : 'none';
      }});
    }}
  </script>
</body>
</html>"""
    return html


def _paper_card_html(p: dict) -> str:
    score = p.get("relevance_score", 0)
    score_class = "score-high" if score >= 8 else "score-mid" if score >= 6 else "score-low"

    authors = p.get("authors", [])
    if len(authors) > 5:
        author_str = ", ".join(_esc(a) for a in authors[:5]) + f" et al."
    else:
        author_str = ", ".join(_esc(a) for a in authors)

    cats = ", ".join(p.get("categories", []))

    # TL;DR
    summary = p.get("summary", {})
    tldr_html = ""
    if isinstance(summary, dict) and summary.get("tldr", "N/A") != "N/A":
        tldr_html = f'<div class="tldr">{_esc(summary["tldr"])}</div>'

    # Reason
    reason = p.get("relevance_reason", "")
    reason_html = f'<div class="reason">Why: {_esc(reason)}</div>' if reason else ""

    # Code
    code = p.get("code")
    code_html = ""
    if code:
        stars_str = f" ({code.get('stars', '?')} stars)" if "stars" in code else ""
        code_html = f'<span class="code-badge">CODE</span> <a href="{_esc(code["url"])}">{_esc(code["url"])}</a>{stars_str}'

    # Links
    pdf_url = p.get("pdf_url", "")
    abs_url = p.get("abs_url", "")

    return f"""
    <div class="paper-card" data-score="{score}">
      <div class="paper-title">
        <a href="{_esc(abs_url)}">{_esc(p['title'])}</a>
        <span class="score {score_class}">{score}/10</span>
      </div>
      <div class="meta">{author_str} &middot; {cats}</div>
      {tldr_html}
      {reason_html}
      <div class="links">
        <a href="{_esc(pdf_url)}">PDF</a>
        <a href="{_esc(abs_url)}">Abstract</a>
        {code_html}
      </div>
    </div>"""


def _esc(text: str) -> str:
    """Basic HTML escaping."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def save_outputs(
    papers_by_profile: dict[str, list],
    output_config: dict,
    data_dir: str = "data",
    docs_dir: str = "docs",
    threshold: int = 6,
) -> list[Path]:
    """Save Markdown and/or HTML outputs. Returns list of created files."""
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    created = []

    if output_config.get("markdown", True):
        md = generate_markdown(papers_by_profile, date_str, threshold)
        md_dir = Path(data_dir) / date_str[:4]  # YYYY
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = md_dir / f"{date_str}.md"
        md_path.write_text(md, encoding="utf-8")
        created.append(md_path)
        print(f"  Saved Markdown: {md_path}")

    if output_config.get("html", True):
        html = generate_html(papers_by_profile, date_str, threshold)
        docs_path = Path(docs_dir)
        docs_path.mkdir(parents=True, exist_ok=True)
        html_path = docs_path / "index.html"
        html_path.write_text(html, encoding="utf-8")
        created.append(html_path)
        print(f"  Saved HTML: {html_path}")

        # Also save a dated copy
        archive_path = docs_path / "archive" / f"{date_str}.html"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_text(html, encoding="utf-8")
        created.append(archive_path)

    # Always save processed JSONL
    jsonl_dir = Path(data_dir) / "processed"
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = jsonl_dir / f"{date_str}.jsonl"
    with open(jsonl_path, "w") as f:
        for profile_name, papers in papers_by_profile.items():
            for p in papers:
                p["_profile"] = profile_name
                f.write(json.dumps(p, ensure_ascii=False) + "\n")
    created.append(jsonl_path)
    print(f"  Saved JSONL: {jsonl_path}")

    return created
