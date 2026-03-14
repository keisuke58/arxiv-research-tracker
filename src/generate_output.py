"""Generate Markdown and HTML output from scored papers."""

import json
import os
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


def _collect_all_categories(papers_by_profile: dict, threshold: int) -> list[str]:
    """Collect all unique categories from relevant papers."""
    cats = set()
    for papers in papers_by_profile.values():
        for p in papers:
            if p.get("relevance_score", 0) >= threshold:
                for c in p.get("categories", []):
                    cats.add(c)
    return sorted(cats)


def _list_archive_dates(docs_dir: str) -> list[str]:
    """List available archive dates from docs/archive/."""
    archive_dir = Path(docs_dir) / "archive"
    if not archive_dir.exists():
        return []
    dates = []
    for f in archive_dir.glob("*.html"):
        dates.append(f.stem)
    return sorted(dates, reverse=True)


def generate_html(
    papers_by_profile: dict[str, list[dict[str, Any]]],
    date_str: str | None = None,
    threshold: int = 6,
    docs_dir: str = "docs",
) -> str:
    """Generate an HTML digest page with full interactive UI."""
    if date_str is None:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    total = sum(len(ps) for ps in papers_by_profile.values())
    relevant = sum(
        1 for ps in papers_by_profile.values()
        for p in ps if p.get("relevance_score", 0) >= threshold
    )

    # Collect profile names and categories for filters
    profile_names = []
    for profile_name, papers in papers_by_profile.items():
        above = [p for p in papers if p.get("relevance_score", 0) >= threshold]
        if above:
            profile_names.append(profile_name)

    all_categories = _collect_all_categories(papers_by_profile, threshold)
    archive_dates = _list_archive_dates(docs_dir)

    # Build profile tab buttons
    profile_tabs_html = '<button class="tab-btn active" onclick="filterProfile(\'all\', this)">All</button>\n'
    for pn in profile_names:
        profile_tabs_html += f'      <button class="tab-btn" onclick="filterProfile(\'{_esc(pn)}\', this)">{_esc(pn)}</button>\n'

    # Build category filter options
    cat_options = '<option value="all">All Categories</option>\n'
    for c in all_categories:
        cat_options += f'        <option value="{_esc(c)}">{_esc(c)}</option>\n'

    # Build archive date links
    archive_html = ""
    if archive_dates:
        date_links = []
        for d in archive_dates[:30]:
            active = ' class="active"' if d == date_str else ""
            date_links.append(f'<a href="archive/{d}.html"{active}>{d}</a>')
        archive_html = f"""
  <details class="date-nav">
    <summary>Date Archive ({len(archive_dates)} digests)</summary>
    <div class="date-list">
      {" ".join(date_links)}
    </div>
  </details>"""

    # Build profile sections
    sections_html = []
    paper_idx = 0
    for profile_name, papers in papers_by_profile.items():
        above = [p for p in papers if p.get("relevance_score", 0) >= threshold]
        if not above:
            continue
        cards = []
        for p in above:
            cards.append(_paper_card_html(p, paper_idx))
            paper_idx += 1
        section = f"""
    <section class="profile-section" data-profile="{_esc(profile_name)}">
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
      --tldr-bg: rgba(88,166,255,0.05); --fav: #d29922;
    }}
    [data-theme="light"] {{
      --bg: #ffffff; --surface: #f6f8fa; --border: #d0d7de;
      --text: #1f2328; --text-muted: #656d76; --accent: #0969da;
      --green: #1a7f37; --orange: #9a6700; --red: #cf222e;
      --tldr-bg: rgba(9,105,218,0.05); --fav: #9a6700;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
      background: var(--bg); color: var(--text); line-height: 1.6;
      max-width: 960px; margin: 0 auto; padding: 20px;
      transition: background 0.3s, color 0.3s;
    }}
    h1 {{ color: var(--accent); margin-bottom: 4px; font-size: 24px; }}
    .header-row {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }}
    .header-controls {{ display: flex; gap: 8px; align-items: center; }}
    .theme-toggle, .fav-toggle {{
      background: var(--surface); border: 1px solid var(--border);
      color: var(--text); border-radius: 8px; padding: 6px 14px;
      cursor: pointer; font-size: 13px; transition: all 0.3s;
    }}
    .theme-toggle:hover, .fav-toggle:hover {{ border-color: var(--accent); }}
    .fav-toggle.active {{ border-color: var(--fav); color: var(--fav); }}
    .stats {{ color: var(--text-muted); margin-bottom: 16px; font-size: 14px; }}

    /* Date archive */
    .date-nav {{ margin-bottom: 16px; }}
    .date-nav summary {{
      cursor: pointer; color: var(--accent); font-size: 14px;
      padding: 6px 0; user-select: none;
    }}
    .date-list {{
      display: flex; flex-wrap: wrap; gap: 6px; padding: 8px 0;
    }}
    .date-list a {{
      color: var(--text-muted); text-decoration: none; font-size: 12px;
      padding: 3px 8px; border-radius: 4px; border: 1px solid var(--border);
      transition: all 0.2s;
    }}
    .date-list a:hover {{ border-color: var(--accent); color: var(--accent); }}
    .date-list a.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}

    /* Profile tabs */
    .profile-tabs {{
      display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px;
    }}
    .tab-btn {{
      background: var(--surface); border: 1px solid var(--border);
      color: var(--text-muted); border-radius: 20px; padding: 5px 14px;
      cursor: pointer; font-size: 13px; transition: all 0.2s;
    }}
    .tab-btn:hover {{ border-color: var(--accent); color: var(--text); }}
    .tab-btn.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}

    /* Filters */
    .filter-bar {{
      margin-bottom: 16px; display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
    }}
    .filter-bar input, .filter-bar select {{
      padding: 7px 12px; border-radius: 6px;
      border: 1px solid var(--border); background: var(--surface);
      color: var(--text); font-size: 13px; transition: all 0.3s;
    }}
    .filter-bar input {{ flex: 1; min-width: 180px; }}
    .filter-bar select {{ min-width: 140px; }}
    .filter-bar input:focus, .filter-bar select:focus {{ outline: none; border-color: var(--accent); }}
    .score-filter {{ display: flex; align-items: center; gap: 4px; font-size: 13px; color: var(--text-muted); }}
    .score-filter input[type="range"] {{ width: 80px; }}

    /* Section */
    h2 {{ color: var(--text); margin: 20px 0 10px; border-bottom: 1px solid var(--border); padding-bottom: 8px; font-size: 18px; }}
    .badge {{
      background: var(--accent); color: #fff; border-radius: 12px;
      padding: 2px 10px; font-size: 13px; font-weight: 600;
    }}
    [data-theme="light"] .badge {{ color: #fff; }}

    /* Paper card */
    .paper-card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; padding: 14px 16px; margin-bottom: 10px;
      transition: background 0.3s, border-color 0.3s;
      position: relative;
    }}
    .paper-card:hover {{ border-color: var(--accent); }}
    .paper-card.read {{ opacity: 0.6; }}
    .paper-card.read:hover {{ opacity: 1; }}
    .paper-title {{ font-size: 15px; font-weight: 600; margin-bottom: 4px; padding-right: 60px; }}
    .paper-title a {{ color: var(--accent); text-decoration: none; }}
    .paper-title a:hover {{ text-decoration: underline; }}

    /* Card actions (fav + read) */
    .card-actions {{
      position: absolute; top: 12px; right: 12px;
      display: flex; gap: 6px;
    }}
    .card-actions button {{
      background: none; border: none; cursor: pointer;
      font-size: 16px; opacity: 0.4; transition: opacity 0.2s;
      padding: 2px;
    }}
    .card-actions button:hover {{ opacity: 0.8; }}
    .card-actions button.active {{ opacity: 1; }}
    .btn-fav.active {{ color: var(--fav); }}
    .btn-read.active {{ color: var(--green); }}

    .score {{
      display: inline-block; padding: 2px 8px; border-radius: 4px;
      font-size: 12px; font-weight: 700; margin-left: 8px; color: #fff;
    }}
    .score-high {{ background: var(--green); }}
    .score-mid {{ background: var(--orange); }}
    .score-low {{ background: var(--text-muted); }}

    /* Quality score (100pt) */
    .quality-score {{
      display: inline-flex; align-items: center; gap: 4px;
      margin-left: 6px; font-size: 12px;
    }}
    .grade {{
      display: inline-block; padding: 1px 6px; border-radius: 3px;
      font-weight: 800; font-size: 11px; color: #fff;
    }}
    .grade-S {{ background: linear-gradient(135deg, #ff6b6b, #ffd93d); }}
    .grade-A {{ background: var(--green); }}
    .grade-B {{ background: var(--accent); }}
    .grade-C {{ background: var(--text-muted); }}
    .grade-D {{ background: #555; }}
    .quality-num {{ color: var(--text-muted); font-size: 11px; }}
    .quality-breakdown {{
      display: none; margin-top: 6px; padding: 8px 10px;
      background: var(--bg); border: 1px solid var(--border); border-radius: 6px;
      font-size: 11px; color: var(--text-muted);
    }}
    .quality-breakdown.show {{ display: block; }}
    .breakdown-bar {{
      display: flex; align-items: center; gap: 6px; margin: 2px 0;
    }}
    .breakdown-bar .bar-label {{ width: 90px; text-align: right; }}
    .breakdown-bar .bar-track {{
      flex: 1; height: 6px; background: var(--border); border-radius: 3px; overflow: hidden;
    }}
    .breakdown-bar .bar-fill {{
      height: 100%; border-radius: 3px; transition: width 0.3s;
    }}
    .breakdown-bar .bar-val {{ width: 30px; font-size: 10px; }}

    .meta {{ font-size: 13px; color: var(--text-muted); margin-bottom: 6px; }}

    /* Abstract */
    .abstract-toggle {{
      background: none; border: none; color: var(--accent);
      cursor: pointer; font-size: 12px; padding: 0; margin-top: 4px;
    }}
    .abstract-toggle:hover {{ text-decoration: underline; }}
    .abstract-content {{
      display: none; margin-top: 6px; padding: 10px 12px;
      background: var(--bg); border-radius: 6px; font-size: 13px;
      line-height: 1.5; color: var(--text-muted);
      border: 1px solid var(--border);
    }}
    .abstract-content.show {{ display: block; }}

    .tldr {{ font-style: italic; margin: 6px 0; padding: 8px 12px;
             border-left: 3px solid var(--accent); background: var(--tldr-bg); font-size: 13px; }}
    .reason {{ font-size: 12px; color: var(--text-muted); margin-top: 4px; }}
    .links {{ margin-top: 6px; font-size: 13px; }}
    .links a {{ color: var(--accent); margin-right: 12px; text-decoration: none; }}
    .links a:hover {{ text-decoration: underline; }}
    .code-badge {{
      display: inline-block; background: var(--green); color: #fff;
      padding: 1px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;
    }}

    /* Counter */
    .visible-count {{
      color: var(--text-muted); font-size: 13px; margin-bottom: 12px;
    }}

    @media (max-width: 600px) {{
      body {{ padding: 12px; }}
      .paper-card {{ padding: 12px; }}
      .filter-bar {{ flex-direction: column; }}
      .profile-tabs {{ gap: 4px; }}
      .tab-btn {{ padding: 4px 10px; font-size: 12px; }}
    }}
  </style>
</head>
<body>
  <div class="header-row">
    <h1>arXiv Digest</h1>
    <div class="header-controls">
      <button class="fav-toggle" onclick="toggleFavFilter()" id="favBtn" title="Show favorites only">Favorites</button>
      <button class="theme-toggle" onclick="toggleTheme()" id="themeBtn">Light</button>
    </div>
  </div>
  <p class="stats">{date_str} &middot; {relevant} relevant / {total} total papers</p>
  {archive_html}

  <div class="profile-tabs">
    {profile_tabs_html}
  </div>

  <div class="filter-bar">
    <input type="text" id="search" placeholder="Filter by title, author, keyword..." oninput="applyFilters()">
    <select id="catFilter" onchange="applyFilters()">
      {cat_options}
    </select>
    <div class="score-filter">
      Score &ge; <span id="scoreVal">{threshold}</span>
      <input type="range" id="scoreFilter" min="1" max="10" value="{threshold}" oninput="document.getElementById('scoreVal').textContent=this.value; applyFilters()">
    </div>
  </div>

  <div class="visible-count" id="visibleCount"></div>

  {''.join(sections_html)}

  <script>
    // State
    let activeProfile = 'all';
    let favOnly = false;

    // localStorage helpers
    function getFavs() {{
      try {{ return JSON.parse(localStorage.getItem('arxiv_favs') || '{{}}'); }}
      catch {{ return {{}}; }}
    }}
    function setFavs(f) {{ localStorage.setItem('arxiv_favs', JSON.stringify(f)); }}
    function getRead() {{
      try {{ return JSON.parse(localStorage.getItem('arxiv_read') || '{{}}'); }}
      catch {{ return {{}}; }}
    }}
    function setRead(r) {{ localStorage.setItem('arxiv_read', JSON.stringify(r)); }}

    // Toggle favorite
    function toggleFav(id, btn) {{
      const favs = getFavs();
      if (favs[id]) {{ delete favs[id]; btn.classList.remove('active'); }}
      else {{ favs[id] = true; btn.classList.add('active'); }}
      setFavs(favs);
      if (favOnly) applyFilters();
    }}

    // Toggle read
    function toggleRead(id, btn) {{
      const reads = getRead();
      const card = btn.closest('.paper-card');
      if (reads[id]) {{
        delete reads[id];
        btn.classList.remove('active');
        card.classList.remove('read');
      }} else {{
        reads[id] = true;
        btn.classList.add('active');
        card.classList.add('read');
      }}
      setRead(reads);
    }}

    // Init fav/read state on load
    function initCardStates() {{
      const favs = getFavs();
      const reads = getRead();
      document.querySelectorAll('.paper-card').forEach(card => {{
        const id = card.dataset.paperId;
        if (favs[id]) card.querySelector('.btn-fav').classList.add('active');
        if (reads[id]) {{
          card.querySelector('.btn-read').classList.add('active');
          card.classList.add('read');
        }}
      }});
    }}

    // Profile tab filter
    function filterProfile(name, btn) {{
      activeProfile = name;
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      applyFilters();
    }}

    // Fav-only toggle
    function toggleFavFilter() {{
      favOnly = !favOnly;
      document.getElementById('favBtn').classList.toggle('active', favOnly);
      applyFilters();
    }}

    // Toggle quality breakdown
    function toggleBreakdown(idx) {{
      const el = document.getElementById('qb-' + idx);
      if (el) el.classList.toggle('show');
    }}

    // Toggle abstract
    function toggleAbstract(idx) {{
      const el = document.getElementById('abs-' + idx);
      const btn = document.getElementById('abs-btn-' + idx);
      if (el.classList.contains('show')) {{
        el.classList.remove('show');
        btn.textContent = 'Show abstract';
      }} else {{
        el.classList.add('show');
        btn.textContent = 'Hide abstract';
      }}
    }}

    // Main filter logic
    function applyFilters() {{
      const q = document.getElementById('search').value.toLowerCase();
      const cat = document.getElementById('catFilter').value;
      const minScore = parseInt(document.getElementById('scoreFilter').value);
      const favs = getFavs();
      let visible = 0;
      let totalCards = 0;

      // Profile sections
      document.querySelectorAll('.profile-section').forEach(sec => {{
        if (activeProfile !== 'all' && sec.dataset.profile !== activeProfile) {{
          sec.style.display = 'none';
          return;
        }}
        sec.style.display = '';

        let sectionVisible = 0;
        sec.querySelectorAll('.paper-card').forEach(card => {{
          totalCards++;
          const score = parseInt(card.dataset.score) || 0;
          const cats = card.dataset.categories || '';
          const paperId = card.dataset.paperId || '';
          let show = true;

          // Score filter
          if (score < minScore) show = false;

          // Text search
          if (show && q && !card.textContent.toLowerCase().includes(q)) show = false;

          // Category filter
          if (show && cat !== 'all' && !cats.includes(cat)) show = false;

          // Fav filter
          if (show && favOnly && !favs[paperId]) show = false;

          card.style.display = show ? '' : 'none';
          if (show) {{ visible++; sectionVisible++; }}
        }});

        // Hide section header if no visible cards
        if (sectionVisible === 0 && activeProfile === 'all') {{
          sec.style.display = 'none';
        }}
      }});

      document.getElementById('visibleCount').textContent =
        visible + ' / ' + totalCards + ' papers shown';
    }}

    // Theme
    function toggleTheme() {{
      const html = document.documentElement;
      const current = html.getAttribute('data-theme');
      const next = current === 'light' ? 'dark' : 'light';
      html.setAttribute('data-theme', next);
      localStorage.setItem('theme', next);
      updateBtn(next);
    }}
    function updateBtn(theme) {{
      document.getElementById('themeBtn').textContent = theme === 'light' ? 'Dark' : 'Light';
    }}

    // Init
    (function() {{
      const saved = localStorage.getItem('theme');
      if (saved) {{
        document.documentElement.setAttribute('data-theme', saved);
        updateBtn(saved);
      }} else if (window.matchMedia('(prefers-color-scheme: light)').matches) {{
        document.documentElement.setAttribute('data-theme', 'light');
        updateBtn('light');
      }}
      initCardStates();
      applyFilters();
    }})();
  </script>
</body>
</html>"""
    return html


def _paper_card_html(p: dict, idx: int = 0) -> str:
    score = p.get("relevance_score", 0)
    score_class = "score-high" if score >= 8 else "score-mid" if score >= 6 else "score-low"
    paper_id = _esc(p.get("arxiv_id", f"paper-{idx}"))
    cats = ", ".join(p.get("categories", []))

    # Quality score
    q_score = p.get("quality_score", 0)
    q_grade = p.get("quality_grade", "D")
    q_breakdown = p.get("quality_breakdown", {})

    # Breakdown bars
    breakdown_items = [
        ("Relevance", q_breakdown.get("relevance", 0), 25),
        ("Quantitative", q_breakdown.get("quantitative", 0), 25),
        ("Code/Repro", q_breakdown.get("code_repro", 0), 20),
        ("Novelty", q_breakdown.get("novelty", 0), 15),
        ("Rigor", q_breakdown.get("rigor", 0), 15),
    ]
    bar_colors = ["var(--accent)", "var(--green)", "var(--orange)", "#c678dd", "var(--red)"]
    breakdown_html = ""
    if q_breakdown:
        bars = ""
        for i, (label, val, max_val) in enumerate(breakdown_items):
            pct = int(val / max_val * 100) if max_val > 0 else 0
            color = bar_colors[i % len(bar_colors)]
            bars += f"""
        <div class="breakdown-bar">
          <span class="bar-label">{label}</span>
          <div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>
          <span class="bar-val">{val}/{max_val}</span>
        </div>"""
        breakdown_html = f"""
      <div class="quality-breakdown" id="qb-{idx}">{bars}
      </div>"""

    # Authors
    authors = p.get("authors", [])
    if len(authors) > 5:
        author_str = ", ".join(_esc(a) for a in authors[:5]) + f" et al."
    else:
        author_str = ", ".join(_esc(a) for a in authors)

    # Abstract (collapsible)
    abstract = p.get("abstract", "")
    abstract_html = ""
    if abstract:
        abstract_html = f"""
      <button class="abstract-toggle" id="abs-btn-{idx}" onclick="toggleAbstract({idx})">Show abstract</button>
      <div class="abstract-content" id="abs-{idx}">{_esc(abstract)}</div>"""

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
    <div class="paper-card" data-score="{score}" data-quality="{q_score}" data-categories="{_esc(cats)}" data-paper-id="{paper_id}">
      <div class="card-actions">
        <button class="btn-fav" onclick="toggleFav('{paper_id}', this)" title="Favorite">&#9734;</button>
        <button class="btn-read" onclick="toggleRead('{paper_id}', this)" title="Mark read">&#10003;</button>
      </div>
      <div class="paper-title">
        <a href="{_esc(abs_url)}">{_esc(p['title'])}</a>
        <span class="score {score_class}">{score}/10</span>
        <span class="quality-score">
          <span class="grade grade-{q_grade}" onclick="toggleBreakdown({idx})" style="cursor:pointer" title="Click for breakdown">{q_grade}</span>
          <span class="quality-num">{q_score}/100</span>
        </span>
      </div>
      <div class="meta">{author_str} &middot; {_esc(cats)}</div>
      {tldr_html}
      {reason_html}
      {breakdown_html}
      {abstract_html}
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
        .replace("'", "&#39;")
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
        html = generate_html(papers_by_profile, date_str, threshold, docs_dir=docs_dir)
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
