"""Send notifications (email, Slack) with digest results."""

import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import httpx


def send_notifications(
    papers_by_profile: dict[str, list[dict[str, Any]]],
    notification_config: dict,
    html_content: str = "",
    threshold: int = 6,
) -> None:
    """Send notifications based on config."""
    email_config = notification_config.get("email", {})
    slack_config = notification_config.get("slack", {})

    if email_config.get("enabled"):
        _send_email(papers_by_profile, email_config, html_content)

    if slack_config.get("enabled"):
        _send_slack(papers_by_profile, slack_config, threshold)


def _send_email(
    papers_by_profile: dict,
    email_config: dict,
    html_content: str,
) -> None:
    """Send email digest via SMTP or SendGrid."""
    method = email_config.get("method", "smtp")
    to_addr = email_config.get("to") or os.environ.get("TO_EMAIL", "")
    from_addr = email_config.get("from") or os.environ.get("FROM_EMAIL", "")
    subject_prefix = email_config.get("subject_prefix", "[arXiv Digest]")

    if not to_addr:
        print("  Email: no recipient configured, skipping")
        return

    from datetime import date
    subject = f"{subject_prefix} {date.today().strftime('%Y-%m-%d')}"

    if method == "sendgrid":
        _send_via_sendgrid(from_addr, to_addr, subject, html_content)
    else:
        _send_via_smtp(from_addr, to_addr, subject, html_content)


def _send_via_smtp(from_addr: str, to_addr: str, subject: str, html: str) -> None:
    """Send email via SMTP."""
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", from_addr)
    password = os.environ.get("SMTP_PASSWORD", "")

    if not password:
        print("  Email: SMTP_PASSWORD not set, skipping")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        print(f"  Email sent to {to_addr}")
    except Exception as e:
        print(f"  Email failed: {e}")


def _send_via_sendgrid(from_addr: str, to_addr: str, subject: str, html: str) -> None:
    """Send email via SendGrid API."""
    api_key = os.environ.get("SENDGRID_API_KEY", "")
    if not api_key:
        print("  Email: SENDGRID_API_KEY not set, skipping")
        return

    payload = {
        "personalizations": [{"to": [{"email": to_addr}]}],
        "from": {"email": from_addr},
        "subject": subject,
        "content": [{"type": "text/html", "value": html}],
    }

    try:
        resp = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30.0,
        )
        if 200 <= resp.status_code < 300:
            print(f"  SendGrid email sent to {to_addr}")
        else:
            print(f"  SendGrid failed: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"  SendGrid error: {e}")


def _send_slack(
    papers_by_profile: dict,
    slack_config: dict,
    threshold: int,
) -> None:
    """Send top papers to Slack via webhook."""
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not webhook_url:
        print("  Slack: SLACK_WEBHOOK_URL not set, skipping")
        return

    top_n = slack_config.get("top_n", 10)

    # Collect all relevant papers across profiles
    all_relevant = []
    for profile_name, papers in papers_by_profile.items():
        for p in papers:
            if p.get("relevance_score", 0) >= threshold:
                p["_profile"] = profile_name
                all_relevant.append(p)

    all_relevant.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    top_papers = all_relevant[:top_n]

    if not top_papers:
        print("  Slack: no relevant papers to send")
        return

    from datetime import date
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"arXiv Digest — {date.today()}"},
        },
        {"type": "divider"},
    ]

    for p in top_papers:
        score = p.get("relevance_score", "?")
        profile = p.get("_profile", "")
        tldr = ""
        if isinstance(p.get("summary"), dict):
            tldr = p["summary"].get("tldr", "")

        text = f"*<{p['abs_url']}|{p['title']}>*\n"
        text += f"Score: {score}/10 | {profile}\n"
        if tldr:
            text += f"_{tldr}_"

        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})

    payload = {"blocks": blocks}

    try:
        resp = httpx.post(webhook_url, json=payload, timeout=15.0)
        if resp.status_code == 200:
            print(f"  Slack: sent {len(top_papers)} papers")
        else:
            print(f"  Slack failed: {resp.status_code}")
    except Exception as e:
        print(f"  Slack error: {e}")
