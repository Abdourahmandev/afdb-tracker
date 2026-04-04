"""Quick SMTP test — run from the afdb_job_tracker folder."""
import os
import smtplib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

user = os.environ.get("GMAIL_USER", "")
pwd  = os.environ.get("GMAIL_APP_PASSWORD", "")
to   = os.environ.get("RECIPIENT_EMAIL", user)

print(f"GMAIL_USER       : {user}")
print(f"RECIPIENT_EMAIL  : {to}")
print(f"APP_PASSWORD set : {'yes' if pwd else 'NO — missing!'}")
print()

if not user or not pwd:
    print("ERROR: GMAIL_USER or GMAIL_APP_PASSWORD not set in .env")
    raise SystemExit(1)

print("Connecting to smtp.gmail.com:465 ...")
try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
        server.login(user, pwd)
        print("Login OK.")
        server.sendmail(
            user, to,
            "Subject: AfDB tracker SMTP test\r\n\r\nSMTP test successful - your alerts will arrive here."
        )
        print(f"Test email sent to {to}.")
except smtplib.SMTPAuthenticationError as e:
    print(f"AUTH FAILED: {e}")
    print()
    print("Fix: Go to myaccount.google.com → Security → App passwords")
    print("     Create a new password for 'Mail' and paste it in .env as GMAIL_APP_PASSWORD")
except Exception as e:
    print(f"ERROR: {e}")
