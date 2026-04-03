"""report_generator.py — Generate a self-contained static HTML report from the jobs DB."""

import html as _html
import os
from datetime import date, datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get("DATA_DIR", "/app/data")) / "jobs.duckdb"

# ── Static CSS ────────────────────────────────────────────────────────────────
_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         background: #f0f2f5; color: #1a1a2e; }
  header { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
           color: white; padding: 24px 32px; }
  header h1 { font-size: 1.5rem; font-weight: 700; letter-spacing: .5px; }
  header p  { font-size: .85rem; color: #a0aec0; margin-top: 2px; }

  .stats { display: flex; gap: 16px; padding: 24px 32px; flex-wrap: wrap; }
  .stat-card { background: white; border-radius: 12px; padding: 20px 28px;
               flex: 1; min-width: 140px; box-shadow: 0 2px 8px rgba(0,0,0,.07); }
  .stat-card .val { font-size: 2rem; font-weight: 800; color: #1a1a2e; }
  .stat-card .lbl { font-size: .78rem; color: #718096; margin-top: 4px; text-transform: uppercase;
                    letter-spacing: .6px; }

  .table-wrap { margin: 0 32px 32px; background: white; border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,.07); overflow: hidden; }
  .table-head { padding: 18px 24px; border-bottom: 1px solid #edf2f7;
                display: flex; justify-content: space-between; align-items: center; }
  .table-head h2 { font-size: 1rem; font-weight: 600; }
  .table-head small { color: #718096; font-size: .8rem; }

  table { width: 100%; border-collapse: collapse; font-size: .875rem; }
  thead th { background: #f7fafc; padding: 12px 14px; text-align: left;
             font-weight: 600; font-size: .78rem; color: #4a5568; text-transform: uppercase;
             letter-spacing: .5px; border-bottom: 2px solid #edf2f7;
             cursor: pointer; user-select: none; white-space: nowrap; }
  thead th:hover { background: #edf2f7; }
  thead th .sort-icon { margin-left: 4px; color: #a0aec0; font-size: .7rem; }
  thead th.sorted .sort-icon { color: #3182ce; }
  tbody tr { border-bottom: 1px solid #f0f4f8; transition: background .15s; }
  tbody tr:hover { background: #f7fafc; }
  tbody td { padding: 14px 14px; vertical-align: middle; }

  .badge { display: inline-block; width: 52px; text-align: center;
           padding: 5px 0; border-radius: 20px; font-weight: 700; font-size: .85rem; }
  .badge-green  { background: #c6f6d5; color: #22543d; }
  .badge-blue   { background: #bee3f8; color: #1a365d; }
  .badge-grey   { background: #edf2f7; color: #4a5568; }
  .badge-yellow { background: #fefcbf; color: #744210; font-size: .72rem; font-weight: 600; }

  .job-title { font-weight: 600; color: #1a1a2e; }
  .job-id    { display: block; font-size: .72rem; color: #718096; margin-top: 2px; }
  .email-sent { color: #38a169; font-size: .82rem; font-weight: 600; }
  .email-no   { color: #a0aec0; font-size: .82rem; }
  .location-pill { background: #edf2f7; color: #4a5568; border-radius: 6px;
                   padding: 3px 8px; font-size: .78rem; }
  .contract-pill { background: #ebf8ff; color: #2c5282; border-radius: 6px;
                   padding: 3px 8px; font-size: .78rem; }
  td.deadline { font-size: .82rem; color: #4a5568; white-space: nowrap; }
  td.deadline.soon { color: #c05621; font-weight: 600; }

  details { cursor: pointer; }
  details summary { font-size: .82rem; color: #3182ce; list-style: none;
                    outline: none; white-space: nowrap; }
  details summary::-webkit-details-marker { display: none; }
  details summary::before { content: "\\25B6  "; font-size: .6rem; }
  details[open] summary::before { content: "\\25BC  "; }
  details .detail-body { margin-top: 8px; font-size: .82rem; color: #4a5568;
                         line-height: 1.55; max-width: 460px; white-space: pre-wrap;
                         word-break: break-word; }

  .apply-btn { display: inline-block; padding: 6px 14px; border-radius: 8px;
               background: #1a1a2e; color: white; text-decoration: none;
               font-size: .78rem; font-weight: 600; white-space: nowrap;
               transition: background .2s; }
  .apply-btn:hover { background: #2d3748; }

  tr.unevaluated td { color: #a0aec0; }
  tr.unevaluated .job-title { color: #718096; font-weight: 500; }
  .not-eval-label { font-size: .8rem; color: #a0aec0; font-style: italic; }

  .history-wrap { margin: 0 32px 28px; background: white; border-radius: 12px;
                  box-shadow: 0 2px 8px rgba(0,0,0,.07); overflow: hidden; }
  .history-wrap > details > summary { display: flex; justify-content: space-between;
    align-items: center; padding: 18px 24px; border-bottom: 1px solid transparent;
    cursor: pointer; list-style: none; user-select: none; }
  .history-wrap > details > summary::-webkit-details-marker { display: none; }
  .history-wrap > details[open] > summary { border-bottom-color: #edf2f7; }
  .history-wrap > details > summary:hover { background: #f7fafc; }
  .history-wrap > details > summary h2 { font-size: 1rem; font-weight: 600;
    display: flex; align-items: center; gap: 8px; }
  .history-wrap > details > summary .chevron { font-size: .75rem; color: #a0aec0;
    transition: transform .2s; }
  .history-wrap > details[open] > summary .chevron { transform: rotate(90deg); }
  .history-wrap > details > summary small { color: #718096; font-size: .8rem; }
  .history-wrap table thead th { cursor: default; }
  .history-wrap table thead th:hover { background: #f7fafc; }

  .run-status-ok  { display: inline-block; padding: 3px 10px; border-radius: 12px;
                    background: #c6f6d5; color: #22543d; font-size: .75rem; font-weight: 700; }
  .run-status-err { display: inline-block; padding: 3px 10px; border-radius: 12px;
                    background: #fed7d7; color: #742a2a; font-size: .75rem; font-weight: 700; }
  .new-jobs-pill  { display: inline-block; padding: 2px 9px; border-radius: 12px;
                    background: #fefcbf; color: #744210; font-size: .78rem; font-weight: 700; }
  .zero-pill      { color: #a0aec0; font-size: .82rem; }
  .duration-cell  { font-size: .82rem; color: #4a5568; white-space: nowrap; }
  .trigger-manual { background: #ebf8ff; color: #2c5282; border-radius: 6px;
                    padding: 2px 8px; font-size: .75rem; }
  .trigger-sched  { background: #f0fff4; color: #276749; border-radius: 6px;
                    padding: 2px 8px; font-size: .75rem; }
  .run-notes      { font-size: .78rem; color: #718096; font-style: italic; }

  footer { text-align: center; padding: 20px; font-size: .78rem; color: #a0aec0; }

  @media (max-width: 900px) {
    .stats { padding: 16px; }
    .table-wrap { margin: 0 8px 24px; }
    .history-wrap { margin: 0 8px 28px; }
    header { padding: 16px; }
  }
"""

# ── Static JS ─────────────────────────────────────────────────────────────────
_JS = """
  let sortDir = {};
  function sortTable(col) {
    const table = document.getElementById("jobTable");
    const tbody = table.tBodies[0];
    const rows  = Array.from(tbody.rows);
    const asc   = !sortDir[col];
    sortDir     = {};
    sortDir[col] = asc;
    table.querySelectorAll("thead th").forEach(th => {
      th.classList.remove("sorted");
      th.querySelector(".sort-icon").textContent = "\u21c5";
    });
    const th = table.querySelectorAll("thead th")[col];
    th.classList.add("sorted");
    th.querySelector(".sort-icon").textContent = asc ? "\u2191" : "\u2193";
    rows.sort((a, b) => {
      const va = a.cells[col].dataset.val || "";
      const vb = b.cells[col].dataset.val || "";
      const na = parseFloat(va), nb = parseFloat(vb);
      if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
      return asc ? va.localeCompare(vb) : vb.localeCompare(va);
    });
    rows.forEach(r => tbody.appendChild(r));
  }
"""

# ── Page header (static, built once at import time) ───────────────────────────
_PAGE_HEAD = (
    '<!DOCTYPE html>\n<html lang="en">\n<head>\n'
    '<meta charset="UTF-8" />\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n'
    '<title>AfDB Job Tracker \u2014 Dashboard</title>\n'
    '<style>\n' + _CSS + '\n</style>\n</head>\n<body>\n\n'
    '<header>\n'
    '  <h1>AfDB Job Tracker</h1>\n'
    '  <p>African Development Bank \u00b7 Automated pipeline report</p>\n'
    '</header>\n\n'
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _e(s) -> str:
    """HTML-escape a value, return empty string for None."""
    return _html.escape(str(s)) if s is not None else ""


def _score_badge(score) -> str:
    if score is None:
        return '<span class="badge badge-yellow">\u2014</span>'
    if score >= 9:
        return f'<span class="badge badge-green">{score}/10</span>'
    if score >= 7:
        return f'<span class="badge badge-blue">{score}/10</span>'
    return f'<span class="badge badge-grey">{score}/10</span>'


def _deadline_cell(deadline_str) -> str:
    """Return the full <td> element for deadline, with 'soon' warning if ≤7 days away."""
    if not deadline_str:
        return '<td class="deadline" data-val="">\u2014</td>'
    d_str = str(deadline_str)[:10]
    try:
        d = datetime.strptime(d_str, "%Y-%m-%d").date()
        if (d - date.today()).days <= 7:
            return (f'<td class="deadline soon" data-val="{d_str}">'
                    f'{d_str} \u26a0</td>')
    except ValueError:
        pass
    return f'<td class="deadline" data-val="{d_str}">{d_str}</td>'


def _fmt_duration(s) -> str:
    if s is None:
        return "\u2014"
    if s < 60:
        return f"{s:.1f} s"
    return f"{int(s // 60)} m {int(s % 60):02d} s"


def _contract_style(contract: str) -> str:
    c = (contract or "").lower()
    if c in ("staff", "permanent"):
        return ' style="background:#faf5ff;color:#553c9a;"'
    if c == "short-term":
        return ' style="background:#f0fff4;color:#276749;"'
    return ""


# ── Row builders ──────────────────────────────────────────────────────────────

def _build_job_rows(jobs: list[dict]) -> str:
    parts = []
    for j in jobs:
        score = j["score"]
        uneval = score is None
        tr_cls = ' class="unevaluated"' if uneval else ""
        score_val = str(score) if score is not None else "-1"

        title    = _e(j.get("title"))
        job_id   = _e(j.get("job_id"))
        location = _e(j.get("location"))
        contract = _e(j.get("contract_type"))
        url      = _e(j.get("url") or "#")
        summary  = _e(j.get("summary"))
        desc     = _e(j.get("description_raw") or "")

        badge        = _score_badge(score)
        deadline_td  = _deadline_cell(j.get("deadline"))

        # Location / contract pill styles for unevaluated rows
        if uneval:
            loc_style = ' style="background:#f7fafc;color:#a0aec0;"'
            ct_style  = ' style="background:#f7fafc;color:#a0aec0;"'
        else:
            loc_style = ""
            ct_style  = _contract_style(contract)

        # Email cell
        if j.get("email_sent"):
            email_cell, email_val = '<span class="email-sent">\u2705 Sent</span>', "1"
        else:
            email_cell, email_val = '<span class="email-no">\u2014 Not sent</span>', "0"
        if uneval:
            email_val = "-1"

        # Summary / description cell
        if uneval:
            summary_td = '<span class="not-eval-label">Not evaluated yet</span>'
        else:
            parts_inner = []
            if summary:
                parts_inner.append(
                    f'<details><summary>Show AI summary</summary>'
                    f'<div class="detail-body">{summary}</div></details>'
                )
            if desc:
                parts_inner.append(
                    f'<details style="margin-top:6px;"><summary>Show full description</summary>'
                    f'<div class="detail-body">{desc}</div></details>'
                )
            summary_td = "\n          ".join(parts_inner)

        apply_style = ' style="background:#a0aec0;"' if uneval else ""

        parts.append(
            f'      <tr{tr_cls}>\n'
            f'        <td data-val="{score_val}">{badge}</td>\n'
            f'        <td data-val="{title}">'
            f'<span class="job-title">{title}</span>'
            f'<span class="job-id">{job_id}</span></td>\n'
            f'        <td data-val="{location}">'
            f'<span class="location-pill"{loc_style}>{location}</span></td>\n'
            f'        <td data-val="{contract}">'
            f'<span class="contract-pill"{ct_style}>{contract}</span></td>\n'
            f'        {deadline_td}\n'
            f'        <td data-val="{email_val}">{email_cell}</td>\n'
            f'        <td>{summary_td}</td>\n'
            f'        <td><a class="apply-btn" href="{url}" target="_blank"'
            f'{apply_style}>View &amp; Apply \u2192</a></td>\n'
            f'      </tr>'
        )
    return "\n".join(parts)


def _build_history_rows(runs: list[dict]) -> str:
    if not runs:
        return ('<tr><td colspan="9" style="text-align:center;color:#a0aec0;padding:24px;">'
                'No runs recorded yet.</td></tr>')
    parts = []
    for r in runs:
        run_at = r["run_at"]
        run_at_str = (run_at.strftime("%Y-%m-%d %H:%M")
                      if isinstance(run_at, datetime) else str(run_at)[:16])

        trigger = r.get("trigger", "scheduled")
        trigger_cell = (
            '<span class="trigger-manual">\u25b6 Manual</span>'
            if trigger == "manual"
            else '<span class="trigger-sched">\u23f1 Scheduled</span>'
        )

        new_jobs = r.get("new_jobs") or 0
        new_cell = (f'<span class="new-jobs-pill">+{new_jobs} new</span>'
                    if new_jobs > 0
                    else '<span class="zero-pill">\u2014 none</span>')

        status = r.get("status", "ok")
        status_cell = ('<span class="run-status-ok">\u2705 OK</span>'
                       if status == "ok"
                       else '<span class="run-status-err">\u274c Error</span>')

        parts.append(
            f'      <tr>\n'
            f'        <td style="white-space:nowrap;font-size:.82rem;">{run_at_str}</td>\n'
            f'        <td>{trigger_cell}</td>\n'
            f'        <td>{r.get("jobs_in_db", 0)}</td>\n'
            f'        <td>{new_cell}</td>\n'
            f'        <td>{r.get("evaluated", 0)}</td>\n'
            f'        <td>{r.get("emails_sent", 0)}</td>\n'
            f'        <td class="duration-cell">{_fmt_duration(r.get("duration_s"))}</td>\n'
            f'        <td>{status_cell}</td>\n'
            f'        <td class="run-notes">{_e(r.get("notes"))}</td>\n'
            f'      </tr>'
        )
    return "\n".join(parts)


# ── Public entry point ────────────────────────────────────────────────────────

def generate_report() -> Path:
    """Query the DB, build a self-contained HTML report and write it to DATA_DIR/report.html."""
    from db import get_all_jobs_with_evaluations, get_run_history

    jobs = get_all_jobs_with_evaluations()
    runs = get_run_history(limit=20)

    # Stats
    total     = len(jobs)
    evaluated = sum(1 for j in jobs if j["score"] is not None)
    sent      = sum(1 for j in jobs if j.get("email_sent"))
    scores    = [j["score"] for j in jobs if j["score"] is not None]
    avg       = f"{sum(scores)/len(scores):.1f}" if scores else "\u2014"
    top       = sum(1 for s in scores if s >= 9)

    generated_at   = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    job_rows_html  = _build_job_rows(jobs)
    hist_rows_html = _build_history_rows(runs)
    num_runs       = len(runs)

    page = (
        _PAGE_HEAD

        # ── Stats bar ──────────────────────────────────────────────────────
        + f'<div class="stats">\n'
        + f'  <div class="stat-card"><div class="val">{total}</div>'
          f'<div class="lbl">Total Jobs</div></div>\n'
        + f'  <div class="stat-card"><div class="val">{evaluated}</div>'
          f'<div class="lbl">Evaluated</div></div>\n'
        + f'  <div class="stat-card"><div class="val">{sent}</div>'
          f'<div class="lbl">Emails Sent</div></div>\n'
        + f'  <div class="stat-card"><div class="val">{avg}</div>'
          f'<div class="lbl">Avg Score</div></div>\n'
        + f'  <div class="stat-card"><div class="val" style="color:#38a169;">{top}</div>'
          f'<div class="lbl">Score \u2265 9</div></div>\n'
        + f'</div>\n\n'

        # ── Weekly Scan History (collapsible) ──────────────────────────────
        + f'<div class="history-wrap">\n'
          f'  <details>\n'
          f'  <summary>\n'
          f'    <h2><span class="chevron">\u25b6</span> Weekly Scan History</h2>\n'
          f'    <small>Last {num_runs} run(s) &nbsp;\u00b7&nbsp; scheduled every Monday 08:00 UTC</small>\n'
          f'  </summary>\n'
          f'  <table>\n'
          f'    <thead><tr>\n'
          f'      <th>Date &amp; Time (UTC)</th><th>Trigger</th>'
          f'<th>Jobs in DB</th><th>New Jobs</th>'
          f'<th>Evaluated</th><th>Emails Sent</th>'
          f'<th>Duration</th><th>Status</th><th>Notes</th>\n'
          f'    </tr></thead>\n'
          f'    <tbody>\n{hist_rows_html}\n    </tbody>\n'
          f'  </table>\n'
          f'  </details>\n'
          f'</div>\n\n'

        # ── Jobs table ─────────────────────────────────────────────────────
        + f'<div class="table-wrap">\n'
          f'  <div class="table-head">\n'
          f'    <h2>All Jobs</h2>\n'
          f'    <small>Generated: {generated_at} &nbsp;\u00b7&nbsp; {total} jobs tracked</small>\n'
          f'  </div>\n'
          f'  <table id="jobTable">\n'
          f'    <thead><tr>\n'
          f'      <th onclick="sortTable(0)" data-col="0">Score <span class="sort-icon">\u21c5</span></th>\n'
          f'      <th onclick="sortTable(1)" data-col="1">Job Title <span class="sort-icon">\u21c5</span></th>\n'
          f'      <th onclick="sortTable(2)" data-col="2">Location <span class="sort-icon">\u21c5</span></th>\n'
          f'      <th onclick="sortTable(3)" data-col="3">Contract <span class="sort-icon">\u21c5</span></th>\n'
          f'      <th onclick="sortTable(4)" data-col="4">Deadline <span class="sort-icon">\u21c5</span></th>\n'
          f'      <th onclick="sortTable(5)" data-col="5">Email <span class="sort-icon">\u21c5</span></th>\n'
          f'      <th>Summary / Description</th>\n'
          f'      <th>Apply</th>\n'
          f'    </tr></thead>\n'
          f'    <tbody>\n{job_rows_html}\n    </tbody>\n'
          f'  </table>\n'
          f'</div>\n\n'

        # ── Footer + JS ────────────────────────────────────────────────────
        + f'<footer>AfDB Job Tracker \u00b7 Generated {generated_at}</footer>\n\n'
          f'<script>\n{_JS}\n</script>\n'
          f'</body>\n</html>\n'
    )

    out_path = DB_PATH.parent / "report.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path
