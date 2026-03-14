#!/usr/bin/env python3
"""arxiv-research-tracker: daily pipeline orchestrator."""

import argparse
import sys
from pathlib import Path

import yaml

from fetch_papers import fetch_all_papers, save_raw_papers
from score_relevance import score_papers
from summarize import summarize_papers
from detect_code import detect_code_links
from generate_output import generate_html, save_outputs
from notify import send_notifications


def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def run_pipeline(config: dict, skip_notify: bool = False) -> None:
    """Run the full paper collection and analysis pipeline."""
    global_cfg = config.get("global", {})
    llm_cfg = config.get("llm", {})
    scoring_cfg = config.get("scoring", {})
    output_cfg = config.get("output", {})
    notification_cfg = config.get("notification", {})
    code_cfg = config.get("code_detection", {})
    profiles = config.get("profiles", [])

    days_back = global_cfg.get("days_back", 1)
    max_papers = global_cfg.get("max_papers_per_category", 200)
    language = global_cfg.get("language", "English")
    threshold = scoring_cfg.get("threshold", 6)
    batch_size = llm_cfg.get("scoring_batch_size", 8)

    enabled_profiles = [p for p in profiles if p.get("enabled", True)]
    if not enabled_profiles:
        print("No enabled profiles found in config.")
        sys.exit(1)

    print(f"=== arxiv-research-tracker ===")
    print(f"Profiles: {len(enabled_profiles)} enabled")
    print()

    # Step 1: Fetch papers
    print("[1/5] Fetching papers from arXiv...")
    papers_by_profile = fetch_all_papers(
        enabled_profiles,
        max_papers_per_category=max_papers,
        days_back=days_back,
    )
    raw_path = save_raw_papers(papers_by_profile)
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
        print(f"  [{name}] Scoring {len(papers)} papers...")
        papers_by_profile[name] = score_papers(
            papers, interest, llm_cfg, batch_size=batch_size, threshold=threshold
        )
    print()

    # Step 3: Summarize top papers
    print("[3/5] Generating summaries...")
    for profile in enabled_profiles:
        name = profile["name"]
        papers = papers_by_profile.get(name, [])
        # Only summarize papers above threshold
        to_summarize = [p for p in papers if p.get("relevance_score", 0) >= threshold]
        if not to_summarize:
            continue
        print(f"  [{name}] Summarizing {len(to_summarize)} papers...")
        summarize_papers(to_summarize, llm_cfg, language=language)
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
        threshold=threshold,
    )

    # Notify
    if not skip_notify:
        print()
        print("Sending notifications...")
        html_content = ""
        if output_cfg.get("html", True):
            html_path = Path("docs") / "index.html"
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
        help="Fetch only, no LLM calls (useful for testing)",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if args.dry_run:
        # Only fetch and save raw papers
        profiles = [p for p in config.get("profiles", []) if p.get("enabled", True)]
        print("=== DRY RUN (fetch only) ===")
        papers = fetch_all_papers(
            profiles,
            max_papers_per_category=config.get("global", {}).get("max_papers_per_category", 200),
            days_back=config.get("global", {}).get("days_back", 1),
        )
        save_raw_papers(papers)
        print("=== Done (dry run) ===")
    else:
        run_pipeline(config, skip_notify=args.skip_notify)


if __name__ == "__main__":
    main()
