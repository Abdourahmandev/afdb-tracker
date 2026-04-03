"""
notifier.py — Send a Gmail alert for a high-scoring job match.
Uses Gmail SMTP with an App Password (not your regular Google password).
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SCORE_COLORS = {
    range(9, 11): "#2e7d32",  # dark green  — excellent
    range(7, 9):  "#1565c0",  # dark blue   — good
    range(5, 7):  "#e65100",  # orange      — partial
}


def _score_color(score: int) -> str:
    for r, color in SCORE_COLORS.items():
        if score in r:
            return color
    return "#b71c1c"  # red — weak


def _build_html(job: dict, score: int, summary: str) -> str:
    color = _score_color(score)
    title = job.get("title", "Unknown Position")
    location = job.get("location") or "Not specified"
    contract_type = job.get("contract_type") or "Not specified"
    deadline = job.get("deadline") or "Not specified"
    url = job.get("url", "#")

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="font-family: Arial, sans-serif; max-width: 640px; margin: auto; padding: 20px; color: #333;">

  <div style="background-color: #f5f5f5; border-left: 6px solid {color}; padding: 16px 20px; margin-bottom: 24px;">
    <h2 style="margin: 0 0 6px 0; color: {color};">
      &#127942; Match Score: {score}/10
    </h2>
    <p style="margin: 0; font-size: 18px; font-weight: bold;">{title}</p>
  </div>

  <h3 style="color: #555; border-bottom: 1px solid #ddd; padding-bottom: 6px;">Job Overview</h3>
  <p style="line-height: 1.6;">{summary}</p>

  <h3 style="color: #555; border-bottom: 1px solid #ddd; padding-bottom: 6px;">Key Details</h3>
  <table style="width: 100%; border-collapse: collapse;">
    <tr>
      <td style="padding: 8px; background: #fafafa; font-weight: bold; width: 140px;">Location</td>
      <td style="padding: 8px;">{location}</td>
    </tr>
    <tr>
      <td style="padding: 8px; background: #f0f0f0; font-weight: bold;">Contract Type</td>
      <td style="padding: 8px; background: #f8f8f8;">{contract_type}</td>
    </tr>
    <tr>
      <td style="padding: 8px; background: #fafafa; font-weight: bold;">Deadline</td>
      <td style="padding: 8px;">{deadline}</td>
    </tr>
  </table>

  <div style="margin-top: 28px; text-align: center;">
    <a href="{url}"
       style="background-color: {color}; color: white; padding: 12px 28px;
              text-decoration: none; border-radius: 4px; font-size: 16px;
              display: inline-block;">
      View &amp; Apply →
    </a>
  </div>

  <hr style="margin-top: 32px; border: none; border-top: 1px solid #eee;">
  <p style="font-size: 12px; color: #999; text-align: center;">
    AfDB Job Tracker — automated alert. Unsubscribe by stopping the Docker container.
  </p>
</body>
</html>"""


def send_alert(job: dict, score: int, summary: str) -> None:
    """Send an HTML email alert for a matched job."""
    gmail_user = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    recipient = os.environ.get("RECIPIENT_EMAIL", gmail_user)

    title = job.get("title", "New Job Match")
    subject = f"[AfDB] Score {score}/10 — {title}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient

    # Plain-text fallback
    plain = (
        f"AfDB Job Match — Score {score}/10\n\n"
        f"Title: {title}\n"
        f"Location: {job.get('location', 'N/A')}\n"
        f"Contract: {job.get('contract_type', 'N/A')}\n"
        f"Deadline: {job.get('deadline', 'N/A')}\n\n"
        f"Why it matches:\n{summary}\n\n"
        f"Apply here: {job.get('url', '')}"
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_build_html(job, score, summary), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, app_password)
        server.sendmail(gmail_user, recipient, msg.as_string())

    logger.info("Email sent for job %s (score %d) to %s", job.get("job_id"), score, recipient)
