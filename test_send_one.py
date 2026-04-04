"""Test send_alert directly on the first pending job."""
import os, sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
sys.path.insert(0, 'src')

from db import get_unemailed_jobs, mark_email_sent
from notifier import send_alert

threshold = int(os.environ.get('SCORE_THRESHOLD', 7))
pending = get_unemailed_jobs(threshold)
print(f"Pending unemailed jobs: {len(pending)}")

if not pending:
    print("Nothing to send.")
else:
    job = pending[0]
    print(f"Testing send_alert for: [{job['job_id']}] {job['title']} (score {job['score']})")
    try:
        send_alert(job, job['score'], job['summary'])
        mark_email_sent(job['job_id'])
        print("SUCCESS — email sent and marked.")
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
