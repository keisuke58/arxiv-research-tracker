#!/usr/bin/env python3
"""arxiv-research-tracker: daily pipeline orchestrator."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

from fetch_papers import fetch_all_papers, save_raw_papers
from score_relevance import score_papers
from keyword_scorer import score_by_keywords
from embedding_scorer import score_by_embedding
from summarize import summarize_papers
from detect_code import detect_code_links
from generate_output import save_outputs
from notify import send_notifications


def load_config(config_path: str = "config.yaml") -> dict:
    config_file = Path(config_path).resolve()
    with open(config_file) as f:
        config = yaml.safe_load(f)
    config["_project_root"] = config_file.parent
    return config


def _load_state(state_path: Path) -> dict:
    """Load pipeline state (last run date, etc.)."""
    if state_path.exists():
        return json.loads(state_path.read_text())
    return {}


def _save_state(state_path: Path, state: dict) -> None:
    """Save pipeline state."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))


def _compute_days_back(state: dict, default: int = 1) -> int:
    """Compute days_back from last run date, handling weekends."""
    last_run = state.get("last_run_date")
    if not last_run:
        return default
    try:
        last = datetime.strptime(last_run, "%Y-%m-%d")
        delta = (datetime.utcnow() - last).days
        return max(delta, 1)
    except ValueError:
        return default


def run_pipeline(
    config: dict,
    skip_notify: bool = False,
    scoring_mode: str = "keyword",
) -> None:
    """Run the full paper collection and analysis pipeline."""
    global_cfg = config.get("global", {})
    llm_cfg = config.get("llm", {})
    scoring_cfg = config.get("scoring", {})
    output_cfg = config.get("output", {})
    notification_cfg = config.get("notification", {})
    code_cfg = config.get("code_detection", {})
    profiles = config.get("profiles", [])

    project_root = config.get("_project_root", Path.cwd())
    data_dir = str(project_root / "data")
    docs_dir = str(project_root / "docs")
    state_path = project_root / "data" / ".state.json"

    max_papers = global_cfg.get("max_papers_per_category", 200)
    language = global_cfg.get("language", "English")
    threshold = scoring_cfg.get("threshold", 6)
    batch_size = llm_cfg.get("scoring_batch_size", 8)

    # Auto-compute days_back from last run
    state = _load_state(state_path)
    days_back_cfg = global_cfg.get("days_back", 1)
    days_back = _compute_days_back(state, default=days_back_cfg)

    enabled_profiles = [p for p in profiles if p.get("enabled", True)]
    if not enabled_profiles:
        print("No enabled profiles found in config.")
        sys.exit(1)

    print(f"=== arxiv-research-tracker ({scoring_mode} mode) ===")
    print(f"Profiles: {len(enabled_profiles)} enabled, days_back={days_back}")
    print()

    # Step 1: Fetch papers
    print("[1/5] Fetching papers from arXiv...")
    papers_by_profile = fetch_all_papers(
        enabled_profiles,
        max_papers_per_category=max_papers,
        days_back=days_back,
    )
    save_raw_papers(papers_by_profile, data_dir=data_dir)
    print()

    # Step 2: Score relevance
    print("[2/5] Scoring relevance...")
    for profile in enabled_profiles:
        name = profile["name"]
        papers = papers_by_profile.get(name, [])
        if not papers:
            continue
        interest = profile.get("interest", "")
        if not interest:
            print(f"  [{name}] No interest defined, skipping scoring")
            continue
        print(f"  [{name}] Scoring {len(papers)} papers ({scoring_mode})...")
        if scoring_mode == "llm":
            papers_by_profile[name] = score_papers(
                papers, interest, llm_cfg, batch_size=batch_size, threshold=threshold
            )
        elif scoring_mode == "embedding":
            papers_by_profile[name] = score_by_embedding(
                papers, interest, threshold=threshold
            )
        else:
            papers_by_profile[name] = score_by_keywords(
                papers, interest, threshold=threshold
            )
    print()

    # Step 3: Summarize top papers (LLM only)
    if scoring_mode == "llm":
        print("[3/5] Generating summaries...")
        for profile in enabled_profiles:
            name = profile["name"]
            papers = papers_by_profile.get(name, [])
            to_summarize = [p for p in papers if p.get("relevance_score", 0) >= threshold]
            if not to_summarize:
                continue
            print(f"  [{name}] Summarizing {len(to_summarize)} papers...")
            summarize_papers(to_summarize, llm_cfg, language=language)
        print()
    else:
        print(f"[3/5] Summaries skipped ({scoring_mode} mode)")
        print()

    # Step 4: Detect code
    if code_cfg.get("enabled", True):
        print("[4/5] Detecting code links...")
        for name, papers in papers_by_profile.items():
            relevant = [p for p in papers if p.get("relevance_score", 0) >= threshold]
            if relevant:
                detect_code_links(
                    relevant,
                    check_metadata=code_cfg.get("check_github_metadata", True),
                    star_threshold=code_cfg.get("star_threshold", 10),
                )
        print()
    else:
        print("[4/5] Code detection disabled, skipping")
        print()

    # Step 5: Generate output
    print("[5/5] Generating output...")
    created = save_outputs(
        papers_by_profile,
        output_cfg,
        data_dir=data_dir,
        docs_dir=docs_dir,
        threshold=threshold,
    )

    # Save state
    _save_state(state_path, {
        "last_run_date": datetime.utcnow().strftime("%Y-%m-%d"),
        "scoring_mode": scoring_mode,
        "total_papers": sum(len(ps) for ps in papers_by_profile.values()),
    })

    # Notify
    if not skip_notify:
        print()
        print("Sending notifications...")
        html_content = ""
        if output_cfg.get("html", True):
            html_path = Path(docs_dir) / "index.html"
            if html_path.exists():
                html_content = html_path.read_text()
        send_notifications(
            papers_by_profile, notification_cfg, html_content, threshold
        )

    print()
    print("=== Done ===")
    total = sum(len(ps) for ps in papers_by_profile.values())
    relevant = sum(
        1 for ps in papers_by_profile.values()
        for p in ps if p.get("relevance_score", 0) >= threshold
    )
    print(f"Total: {total} papers, {relevant} above threshold")
    for path in created:
        print(f"  {path}")


def main():
    parser = argparse.ArgumentParser(description="arxiv-research-tracker")
    parser.add_argument(
        "--config", default="config.yaml", help="Path to config file"
    )
    parser.add_argument(
        "--skip-notify", action="store_true", help="Skip notifications"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch only, no scoring (useful for testing)",
    )

    scoring_group = parser.add_mutually_exclusive_group()
    scoring_group.add_argument(
        "--llm", action="store_true",
        help="Use LLM for scoring and summaries (requires API key)",
    )
    scoring_group.add_argument(
        "--embedding", action="store_true",
        help="Use sentence embeddings for scoring (requires sentence-transformers)",
    )

    args = parser.parse_args()
    config = load_config(args.config)

    if args.dry_run:
        project_root = config.get("_project_root", Path.cwd())
        profiles = [p for p in config.get("profiles", []) if p.get("enabled", True)]
        print("=== DRY RUN (fetch only) ===")
        papers = fetch_all_papers(
            profiles,
            max_papers_per_category=config.get("global", {}).get("max_papers_per_category", 200),
            days_back=config.get("global", {}).get("days_back", 1),
        )
        save_raw_papers(papers, data_dir=str(project_root / "data"))
        print("=== Done (dry run) ===")
    else:
        scoring_mode = "llm" if args.llm else "embedding" if args.embedding else "keyword"
        run_pipeline(config, skip_notify=args.skip_notify, scoring_mode=scoring_mode)


if __name__ == "__main__":
    main()
