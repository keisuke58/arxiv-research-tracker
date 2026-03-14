"""Detect GitHub repository links in paper abstracts and fetch metadata."""

import os
import re
from typing import Any

import httpx


GITHUB_REPO_PATTERN = re.compile(
    r"https?://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+)"
)
GITHUB_IO_PATTERN = re.compile(
    r"https?://([a-zA-Z0-9_.-]+)\.github\.io(?:/[a-zA-Z0-9_.-]+)*"
)


def detect_code_links(
    papers: list[dict[str, Any]],
    check_metadata: bool = True,
    star_threshold: int = 10,
) -> list[dict[str, Any]]:
    """Scan abstracts for GitHub URLs and optionally fetch repo metadata."""
    github_token = os.environ.get("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    with httpx.Client(timeout=10.0) as client:
        for paper in papers:
            text = " ".join([
                paper.get("abstract", ""),
                paper.get("title", ""),
                paper.get("comment", ""),  # arXiv comment often has code links
            ])
            code_info = _extract_github_url(text)

            if code_info and check_metadata and "owner" in code_info:
                _fetch_repo_metadata(client, code_info, headers)

            if code_info:
                code_info["is_highlighted"] = code_info.get("stars", 0) >= star_threshold
                paper["code"] = code_info
            else:
                paper["code"] = None

    has_code = sum(1 for p in papers if p.get("code"))
    print(f"  Code detected in {has_code}/{len(papers)} papers")
    return papers


def _extract_github_url(text: str) -> dict | None:
    """Extract the first GitHub repo URL from text."""
    match = GITHUB_REPO_PATTERN.search(text)
    if match:
        owner, repo = match.groups()
        repo = repo.rstrip(".")
        if repo.endswith(".git"):
            repo = repo[:-4]
        return {
            "url": f"https://github.com/{owner}/{repo}",
            "owner": owner,
            "repo": repo,
        }

    match_io = GITHUB_IO_PATTERN.search(text)
    if match_io:
        return {"url": match_io.group(0).rstrip(".,)")}

    return None


def _fetch_repo_metadata(
    client: httpx.Client, code_info: dict, headers: dict
) -> None:
    """Fetch stars and last update from GitHub API."""
    owner = code_info.get("owner", "")
    repo = code_info.get("repo", "")
    if not owner or not repo:
        return

    try:
        resp = client.get(
            f"https://api.github.com/repos/{owner}/{repo}",
            headers=headers,
        )
        if resp.status_code == 200:
            data = resp.json()
            code_info["stars"] = data.get("stargazers_count", 0)
            code_info["last_pushed"] = (data.get("pushed_at") or "")[:10]
            code_info["language"] = data.get("language", "")
            code_info["description"] = data.get("description", "")
    except Exception:
        pass
