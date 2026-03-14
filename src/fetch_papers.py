"""Fetch new papers from arXiv API."""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from lxml import etree


ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


def fetch_papers_for_category(
    category: str,
    max_results: int = 200,
    days_back: int = 1,
) -> list[dict[str, Any]]:
    """Fetch recent papers from a single arXiv category via the API."""
    # arXiv API search query
    query = f"cat:{category}"
    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    papers = []
    cutoff = datetime.utcnow() - timedelta(days=days_back + 1)

    with httpx.Client(timeout=60.0) as client:
        resp = client.get(ARXIV_API_URL, params=params)
        resp.raise_for_status()

    root = etree.fromstring(resp.content)
    entries = root.findall("atom:entry", ATOM_NS)

    for entry in entries:
        published_str = entry.findtext("atom:published", namespaces=ATOM_NS)
        if not published_str:
            continue
        published = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
        if published.replace(tzinfo=None) < cutoff:
            continue

        # Extract categories
        categories = [
            c.get("term", "")
            for c in entry.findall("atom:category", ATOM_NS)
        ]

        # Extract authors
        authors = []
        for author_el in entry.findall("atom:author", ATOM_NS):
            name = author_el.findtext("atom:name", namespaces=ATOM_NS)
            if name:
                authors.append(name)

        # Extract links
        arxiv_id = ""
        pdf_url = ""
        for link in entry.findall("atom:link", ATOM_NS):
            href = link.get("href", "")
            if link.get("type") == "text/html" or (link.get("rel") == "alternate"):
                arxiv_id = href.split("/abs/")[-1] if "/abs/" in href else href
            if link.get("title") == "pdf":
                pdf_url = href

        abstract = entry.findtext("atom:summary", namespaces=ATOM_NS) or ""
        abstract = " ".join(abstract.split())  # normalize whitespace

        # arXiv comment field (often contains "code at github.com/...")
        comment = entry.findtext("arxiv:comment", namespaces=ATOM_NS) or ""
        comment = " ".join(comment.split())

        paper = {
            "arxiv_id": arxiv_id,
            "title": (entry.findtext("atom:title", namespaces=ATOM_NS) or "").strip().replace("\n", " "),
            "authors": authors,
            "abstract": abstract,
            "comment": comment,
            "categories": categories,
            "primary_category": category,
            "published": published_str,
            "pdf_url": pdf_url,
            "abs_url": f"https://arxiv.org/abs/{arxiv_id}",
        }
        papers.append(paper)

    return papers


def fetch_all_papers(
    profiles: list[dict],
    max_papers_per_category: int = 200,
    days_back: int = 1,
) -> dict[str, list[dict[str, Any]]]:
    """Fetch papers for all enabled profiles.

    Returns a dict mapping profile name -> list of papers.
    """
    results = {}
    seen_ids: set[str] = set()

    for profile in profiles:
        if not profile.get("enabled", True):
            continue

        profile_papers = []
        categories = profile.get("categories", [])

        for cat in categories:
            print(f"  Fetching {cat}...")
            papers = fetch_papers_for_category(
                cat,
                max_results=max_papers_per_category,
                days_back=days_back,
            )
            for p in papers:
                if p["arxiv_id"] not in seen_ids:
                    seen_ids.add(p["arxiv_id"])
                    profile_papers.append(p)
            # Be polite to arXiv API
            time.sleep(3.0)

        results[profile["name"]] = profile_papers
        print(f"  [{profile['name']}] {len(profile_papers)} unique papers")

    return results


def save_raw_papers(papers_by_profile: dict[str, list], data_dir: str = "data") -> Path:
    """Save fetched papers to a date-stamped JSONL file."""
    today = datetime.utcnow().strftime("%Y-%m-%d")
    out_dir = Path(data_dir) / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{today}.jsonl"

    all_papers = []
    for profile_name, papers in papers_by_profile.items():
        for p in papers:
            p["_profile"] = profile_name
            all_papers.append(p)

    with open(out_path, "w") as f:
        for paper in all_papers:
            f.write(json.dumps(paper, ensure_ascii=False) + "\n")

    print(f"Saved {len(all_papers)} papers to {out_path}")
    return out_path
