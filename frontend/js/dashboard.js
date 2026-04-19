/**
 * dashboard.js — Job dashboard page logic.
 *
 * Flow:
 *   1. requireAuth() → redirect to index.html if not logged in
 *   2. Load sources for filter dropdown
 *   3. Load first page of jobs
 *   4. Re-load on filter change (debounced 300 ms)
 *   5. Handle prev / next pagination
 */
(function (global) {
  'use strict';

  // ── State ────────────────────────────────────────────────────────────────────

  const state = {
    page:      1,
    limit:     25,
    total:     0,
    source:    '',
    min_score: 0,
    sources:   [],   // full source list from /api/sources
  };

  let debounceTimer = null;

  // ── DOM refs (set after DOMContentLoaded) ────────────────────────────────────

  let elGrid, elTotal, elPage, elPrev, elNext, elSourceFilter,
      elMinScore, elLoading, elEmpty, elNavUser, elNavLogout;

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function sourceBadgeClass(sourceId) {
    const known = ['afdb', 'worldbank', 'undp', 'imf'];
    const id = (sourceId || '').toLowerCase();
    return known.includes(id) ? `badge-source-${id}` : 'badge-source-default';
  }

  function sourceBadgeLabel(sourceId, sources) {
    const src = sources.find(s => s.source_id === sourceId);
    if (src) return src.display_name.replace(/\s*\(.*?\)\s*/g, '').trim();
    return sourceId || 'Unknown';
  }

  function scoreBadge(score) {
    if (score == null) {
      return '<span class="badge badge-score-pending" title="Not yet scored">Pending</span>';
    }
    let cls, label;
    if (score >= 8)      { cls = 'badge-score-high'; label = score + '/10'; }
    else if (score >= 5) { cls = 'badge-score-mid';  label = score + '/10'; }
    else                 { cls = 'badge-score-low';  label = score + '/10'; }
    return `<span class="badge ${cls}" title="Match score">${label}</span>`;
  }

  function formatDeadline(raw) {
    if (!raw) return '';
    try {
      return new Date(raw).toLocaleDateString(undefined, {
        year: 'numeric', month: 'short', day: 'numeric',
      });
    } catch (_) { return raw; }
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Render ───────────────────────────────────────────────────────────────────

  function renderJobs(jobs) {
    // Guard: jobs may be undefined/null if the API returned an unexpected shape
    if (!Array.isArray(jobs) || !jobs.length) {
      elGrid.innerHTML  = '';
      elEmpty.style.display = 'block';
      return;
    }
    elEmpty.style.display = 'none';

    elGrid.innerHTML = jobs.map(job => {
      const srcClass = sourceBadgeClass(job.source_id);
      const srcLabel = sourceBadgeLabel(job.source_id, state.sources);
      const score    = scoreBadge(job.score);
      const deadline = formatDeadline(job.deadline);
      const hasSummary = job.summary && job.summary.trim().length > 0;
      const summaryId  = 'sum-' + escapeHtml(job.job_id);

      return `
<article class="job-card" data-source="${escapeHtml(job.source_id)}">
  <div class="job-card-header">
    <h3 class="job-title">${job.title ? escapeHtml(job.title) : '<span style="color:var(--gray-400);font-style:italic">Position Closed</span>'}</h3>
  </div>
  <div class="job-badges">
    <span class="badge ${srcClass}">${escapeHtml(srcLabel)}</span>
    ${score}
  </div>
  <div class="job-meta">
    ${job.location ? `
    <span class="job-meta-item">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7z"/>
        <circle cx="12" cy="9" r="2.5"/>
      </svg>
      ${escapeHtml(job.location)}
    </span>` : ''}
    ${job.contract_type ? `
    <span class="job-meta-item">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="2" y="7" width="20" height="14" rx="2"/>
        <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
      </svg>
      ${escapeHtml(job.contract_type)}
    </span>` : ''}
    ${deadline ? `
    <span class="job-meta-item">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="4" width="18" height="18" rx="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
      </svg>
      Deadline: ${deadline}
    </span>` : ''}
  </div>
  ${hasSummary ? `
  <div>
    <button class="summary-toggle" onclick="toggleSummary('${summaryId}', this)" aria-expanded="false">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
      AI Summary
    </button>
    <div class="summary-body" id="${summaryId}">${escapeHtml(job.summary)}</div>
  </div>` : ''}
  <div class="job-footer">
    <span style="font-size:0.78rem;color:var(--gray-500)">
      Added ${formatDeadline(job.scraped_at)}
    </span>
    <a href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer"
       class="btn btn-primary btn-sm">
      View &amp; Apply
    </a>
  </div>
</article>`;
    }).join('');
  }

  function updatePagination() {
    const totalPages = Math.ceil(state.total / state.limit) || 1;
    elPage.textContent  = `Page ${state.page} of ${totalPages}`;
    elTotal.textContent = `${state.total} job${state.total !== 1 ? 's' : ''} found`;
    elPrev.disabled = state.page <= 1;
    elNext.disabled = state.page >= totalPages;
  }

  // ── Data loading ─────────────────────────────────────────────────────────────

  async function loadJobs() {
    elLoading.style.display = 'flex';
    elGrid.style.opacity    = '0.4';

    try {
      const resp = await Api.getJobs({
        source:    state.source    || undefined,
        min_score: state.min_score || undefined,
        page:      state.page,
        limit:     state.limit,
      });

      // Guard: extract jobs array and total with safe fallbacks in case the
      // API response shape is unexpected (e.g. error body, proxy response).
      const jobs = Array.isArray(resp.jobs) ? resp.jobs : [];
      state.total = (typeof resp.total === 'number') ? resp.total : jobs.length;
      renderJobs(jobs);
      updatePagination();
    } catch (err) {
      elGrid.innerHTML = `<div class="alert alert-error">${escapeHtml(err.message)}</div>`;
      console.error('dashboard: loadJobs error', err);
    } finally {
      elLoading.style.display = 'none';
      elGrid.style.opacity    = '1';
    }
  }

  async function loadSources() {
    try {
      const resp = await Api.getSources();
      // Guard: sources may be missing if API returns an unexpected shape
      const sources = Array.isArray(resp.sources) ? resp.sources : [];
      state.sources = sources;

      // Build filter dropdown
      elSourceFilter.innerHTML = '<option value="">All sources</option>';
      sources.forEach(src => {
        const opt = document.createElement('option');
        opt.value       = src.source_id;
        opt.textContent = src.display_name.replace(/\s*\(.*?\)\s*/g, '').trim();
        elSourceFilter.appendChild(opt);
      });
    } catch (err) {
      console.warn('dashboard: could not load sources', err);
    }
  }

  // ── Event handlers ───────────────────────────────────────────────────────────

  function onFilterChange() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      state.source    = elSourceFilter.value;
      state.min_score = parseInt(elMinScore.value, 10) || 0;
      state.page      = 1;
      loadJobs();
    }, 300);
  }

  function onPrev() {
    if (state.page > 1) { state.page--; loadJobs(); }
  }

  function onNext() {
    const totalPages = Math.ceil(state.total / state.limit);
    if (state.page < totalPages) { state.page++; loadJobs(); }
  }

  // ── Summary toggle (global, called from inline onclick) ───────────────────────

  global.toggleSummary = function (id, btn) {
    const el = document.getElementById(id);
    if (!el) return;
    const isOpen = el.classList.toggle('open');
    btn.setAttribute('aria-expanded', isOpen);
    const arrow = btn.querySelector('svg');
    if (arrow) arrow.style.transform = isOpen ? 'rotate(180deg)' : '';
  };

  // ── Init ─────────────────────────────────────────────────────────────────────

  async function init() {
    const user = Auth.requireAuth();
    if (!user) return;  // redirected

    // Bind DOM refs
    elGrid         = document.getElementById('job-grid');
    elTotal        = document.getElementById('total-count');
    elPage         = document.getElementById('page-info');
    elPrev         = document.getElementById('btn-prev');
    elNext         = document.getElementById('btn-next');
    elSourceFilter = document.getElementById('filter-source');
    elMinScore     = document.getElementById('filter-min-score');
    elLoading      = document.getElementById('loading-indicator');
    elEmpty        = document.getElementById('empty-state');
    elNavUser      = document.getElementById('nav-user');
    elNavLogout    = document.getElementById('btn-logout');

    // Update nav with user name
    if (elNavUser) elNavUser.textContent = user.name;

    // Logout
    if (elNavLogout) {
      elNavLogout.addEventListener('click', (e) => {
        e.preventDefault();
        Auth.logout();
      });
    }

    // Filter events
    elSourceFilter.addEventListener('change', onFilterChange);
    elMinScore.addEventListener('input', onFilterChange);

    // Pagination
    elPrev.addEventListener('click', onPrev);
    elNext.addEventListener('click', onNext);

    // Initial data load
    await loadSources();
    await loadJobs();
  }

  document.addEventListener('DOMContentLoaded', init);

})(window);
