import duckdb
con = duckdb.connect('data/jobs.duckdb')

print('=== EVALUATIONS TABLE ===')
rows = con.execute('SELECT job_id, score, email_sent, evaluated_at FROM evaluations ORDER BY score DESC').fetchall()
for r in rows:
    print(f'  {r[0]}  score={r[1]}  email_sent={r[2]}  at={r[3]}')

print()
print('Total jobs:', con.execute('SELECT COUNT(*) FROM jobs').fetchone()[0])
print('Total evaluations:', con.execute('SELECT COUNT(*) FROM evaluations').fetchone()[0])
print('Score > 0:', con.execute('SELECT COUNT(*) FROM evaluations WHERE score > 0').fetchone()[0])
print('Email sent:', con.execute('SELECT COUNT(*) FROM evaluations WHERE email_sent = true').fetchone()[0])
con.close()
