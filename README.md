# arxiv-research-tracker

Automated daily arXiv paper collection with LLM-powered relevance scoring, structured summaries, and code detection.

## Features

- **Multi-profile support** — track multiple research areas with separate categories and interests
- **LLM relevance scoring** — papers rated 1-10 based on your natural-language research interests
- **Structured summaries** — TL;DR, motivation, method, result, conclusion for each relevant paper
- **Code detection** — automatically finds GitHub repos linked in papers, fetches star counts
- **Multiple outputs** — Markdown archives, HTML digest (GitHub Pages), email, Slack
- **GitHub Actions** — fully automated daily pipeline, zero infrastructure

## Quick Start

### 1. Fork and configure

```bash
git clone https://github.com/YOUR_USER/arxiv-research-tracker.git
cd arxiv-research-tracker
```

Edit `config.yaml`:
- Enable/disable profiles for your research areas
- Set `interest` in natural language for each profile
- Choose arXiv categories

### 2. Set API keys

For GitHub Actions, add these as repository secrets:
- `LLM_API_KEY` — your LLM API key (DeepSeek, OpenAI, etc.)
- Optional: `SENDGRID_API_KEY`, `SLACK_WEBHOOK_URL`, SMTP credentials

For local use:
```bash
export LLM_API_KEY="your-api-key"
```

### 3. Run locally

```bash
pip install -r requirements.txt

# Full pipeline
cd src && python main.py --config ../config.yaml

# Dry run (fetch only, no LLM calls)
cd src && python main.py --config ../config.yaml --dry-run

# Skip notifications
cd src && python main.py --config ../config.yaml --skip-notify
```

### 4. GitHub Actions

The workflow runs Mon-Fri at 06:00 UTC. You can also trigger manually from the Actions tab.

To enable GitHub Pages: Settings → Pages → Source: "Deploy from a branch" → Branch: `gh-pages`.

## Config Reference

### Profiles

Each profile defines a research area to track:

```yaml
profiles:
  - name: "My Research Area"
    enabled: true
    categories:
      - "cs.LG"      # arXiv category codes
      - "stat.ML"
    interest: |
      Natural language description of what papers
      you want to see. Be specific for better scoring.
```

See [arxiv.org/archive](https://arxiv.org/archive) for all category codes.

### LLM Providers

Supports any OpenAI-compatible API:

```yaml
llm:
  provider: "deepseek"     # or "openai", "anthropic", etc.
  model: "deepseek-chat"
  # base_url: "https://api.deepseek.com"  # auto-set for deepseek
```

### Notifications

- **Email**: SMTP or SendGrid
- **Slack**: webhook URL

## Architecture

```
fetch (arXiv API) → score (LLM) → summarize (LLM) → detect_code (GitHub API) → output + notify
```

| File | Role |
|------|------|
| `src/fetch_papers.py` | arXiv API client, deduplication |
| `src/score_relevance.py` | LLM-based relevance scoring (1-10) |
| `src/summarize.py` | Structured paper summaries |
| `src/detect_code.py` | GitHub URL detection + metadata |
| `src/generate_output.py` | Markdown + HTML generation |
| `src/notify.py` | Email (SMTP/SendGrid) + Slack |
| `src/main.py` | Pipeline orchestrator |

## Output

- `data/raw/YYYY-MM-DD.jsonl` — raw fetched papers
- `data/processed/YYYY-MM-DD.jsonl` — scored + summarized
- `data/YYYY/YYYY-MM-DD.md` — Markdown digest
- `docs/index.html` — latest HTML digest (GitHub Pages)
- `docs/archive/YYYY-MM-DD.html` — archived HTML digests
