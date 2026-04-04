"""Evaluate and email a single high-interest job to preview the new format."""
import sys, os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
sys.path.insert(0, 'src')

import duckdb
from evaluator import evaluate_job
from notifier import send_alert

db = Path(os.environ.get('DATA_DIR', '/app/data')) / 'jobs.duckdb'
con = duckdb.connect(str(db))

# Pick the Senior Data Architect — clearly relevant
job_row = con.execute("""
    SELECT job_id, title, location, contract_type, deadline, description_raw, url
    FROM jobs WHERE job_id = 'AFDB1JP00000807'
""").fetchone()
con.close()

if not job_row:
    print("Job not found — picking first available.")
    con = duckdb.connect(str(db))
    job_row = con.execute("SELECT job_id, title, location, contract_type, deadline, description_raw, url FROM jobs LIMIT 1").fetchone()
    con.close()

keys = ["job_id", "title", "location", "contract_type", "deadline", "description_raw", "url"]
job = dict(zip(keys, job_row))
print(f"Evaluating: [{job['job_id']}] {job['title']}")

result = evaluate_job(job)
print(f"Score: {result['score']}/10")
print(f"Summary:\n{result['summary']}")
print()

send_alert(job, result['score'], result['summary'])
print("Email sent — check your inbox.")
