"""
Reset all evaluations so the pipeline re-evaluates with the new prompt.
Keeps the jobs table intact — only clears evaluations.
"""
import sys
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path('.') / '.env')
sys.path.insert(0, 'src')
import duckdb, os

db = Path(os.environ.get('DATA_DIR', '/app/data')) / 'jobs.duckdb'
con = duckdb.connect(str(db))
count = con.execute('SELECT COUNT(*) FROM evaluations').fetchone()[0]
con.execute('DELETE FROM evaluations')
con.close()
print(f'Cleared {count} evaluation rows. Jobs table untouched.')
print('Next pipeline run will re-evaluate all jobs with the new job-summary prompt.')
