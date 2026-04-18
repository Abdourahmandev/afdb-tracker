"""
notifier_v2.py — Per-user, multi-source email digest for the multi-tenant pipeline.

Sends one digest email per user listing all matched jobs (score >= threshold)
from all their enabled sources, instead of one email per job.
"""
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

# Source badge colors — must match frontend
SOURCE_COLORS: dict[str, str] = {
    "afdb":       "#0066CC",
    "worldbank":  "#009900",
    "undp":       "#6B2FA0",
    "imf":        "#E87722",
}

SCORE_COLORS = {
    range(9, 11): "#2e7d32",
    range(7, 9):  "#1565c0",
    range(5, 7):  "#e65100",
}


def _score_color(score: int) -> str:
    for r, color in SCORE_COLORS.items():
        if score in r:
            return color
    return "#b71c1c"


def _source_color(source_id: str) -> str:
    return SOURCE_COLORS.get(source_id.lower(), "#555555")


def _source_label(source_id: str) -> str:
    labels = {
        "afdb":      "AfDB",
        "worldbank": "World Bank",
        "undp":      "UNDP",
        "imf":       "IMF",
    }
    return labels.get(source_id.lower(), source_id.upper())


def _job_card_html(job: dict, score: int, summary: str) -> str:
    """Render one job as an HTML card for the digest email."""
    score_color = _score_color(score)
    source_id = job.get("source_id", "")
    src_color = _source_color(source_id)
    src_label = _source_label(source_id)

    title = job.get("title", "Unknown Position")
    location = job.get("location") or "Not specified"
    contract_type = job.get("contract_type") or "Not specified"
    deadline = job.get("deadline") or "Not specified"
    url = job.get("url", "#")

    return f"""
  <div style="border: 1px solid #e0e0e0; border-radius: 6px; margin-bottom: 20px; overflow: hidden;">
    <div style="background: #f5f5f5; border-left: 5px solid {score_color}; padding: 12px 16px;">
      <span style="background:{src_color}; color:white; font-size:11px; font-weight:bold;
                   padding:2px 8px; border-radius:10px; margin-right:8px;">{src_label}</span>
      <span style="background:{score_color}; color:white; font-size:11px; font-weight:bold;
                   padding:2px 8px; border-radius:10px;">Score {score}/10</span>
      <p style="margin:8px 0 0 0; font-size:16px; font-weight:bold; color:#222;">{title}</p>
    </div>
    <div style="padding: 12px 16px;">
      <p style="color:#555; line-height:1.5; margin:0 0 10px 0;">{summary}</p>
      <table style="font-size:13px; color:#666;">
        <tr><td style="padding:2px 12px 2px 0; font-weight:bold;">Location</td><td>{location}</td></tr>
        <tr><td style="padding:2px 12px 2px 0; font-weight:bold;">Contract</td><td>{contract_type}</td></tr>
        <tr><td style="padding:2px 12px 2px 0; font-weight:bold;">Deadline</td><td>{deadline}</td></tr>
      </table>
      <a href="{url}"
         style="display:inline-block; margin-top:12px; padding:8px 20px;
                background:{score_color}; color:white; text-decoration:none;
                border-radius:4px; font-size:13px;">
        View &amp; Apply →
      </a>
    </div>
  </div>"""


def _build_digest_html(user: dict, matches: list[tuple[dict, int, str]]) -> str:
    """Build the full digest HTML for a user."""
    name = user.get("name") or user.get("email", "there")
    count = len(matches)
    sources_used = sorted({job.get("source_id", "") for job, _, _ in matches})
    source_labels = ", ".join(_source_label(s) for s in sources_used if s)

    cards = "".join(_job_card_html(job, score, summary) for job, score, summary in matches)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 660px; margin: auto; padding: 20px; color: #333;">

  <div style="background:#1a237e; color:white; padding:20px 24px; border-radius:6px 6px 0 0; margin-bottom:24px;">
    <h1 style="margin:0; font-size:20px;">&#128269; Your Job Matches</h1>
    <p style="margin:6px 0 0 0; opacity:0.85; font-size:14px;">
      Hi {name} — {count} new match{"es" if count != 1 else ""} from {source_labels}
    </p>
  </div>

  {cards}

  <hr style="border:none; border-top:1px solid #eee; margin:32px 0 16px 0;">
  <p style="font-size:12px; color:#999; text-align:center;">
    AfDB-Platform — automated weekly alert.<br>
    Update your preferences at your profile page.
  </p>
</body>
</html>"""


def _build_digest_plain(user: dict, matches: list[tuple[dict, int, str]]) -> str:
    name = user.get("name") or user.get("email", "there")
    lines = [f"Hi {name} — {len(matches)} new job match(es) this week:\n"]
    for job, score, summary in matches:
        lines += [
            f"[{_source_label(job.get('source_id', ''))}] {job.get('title', 'N/A')} — Score {score}/10",
            f"  {summary[:200]}...",
            f"  Apply: {job.get('url', '')}",
            "",
        ]
    return "\n".join(lines)


def send_digest(user: dict, matches: list[tuple[dict, int, str]]) -> None:
    """
    Send a digest email to a user with all their matched jobs.

    Args:
        user:    User document (email, name, notification_email)
        matches: List of (job_dict, score, summary) tuples, sorted by score DESC
    """
    if not matches:
        return

    gmail_user = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = user.get("notification_email") or user.get("email")

    if not recipient:
        logger.warning("User %s has no email — skipping digest", user.get("id"))
        return

    count = len(matches)
    source_labels = ", ".join(
        sorted({_source_label(j.get("source_id", "")) for j, _, _ in matches})
    )
    subject = f"[AfDB-Platform] {count} job match{'es' if count != 1 else ''} — {source_labels}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient

    msg.attach(MIMEText(_build_digest_plain(user, matches), "plain"))
    msg.attach(MIMEText(_build_digest_html(user, matches), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, app_password)
        server.sendmail(gmail_user, recipient, msg.as_string())

    logger.info(
        "Digest sent to %s (%d match(es) from %s)",
        recipient, count, source_labels,
    )
