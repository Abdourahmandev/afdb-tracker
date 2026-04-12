/**
 * profile.js — Profile editor page logic.
 *
 * Note on GET /api/profile:
 *   The current backend exposes only PUT /api/profile (update).
 *   There is no dedicated GET endpoint for the current user's profile.
 *   We pre-fill name from the Auth token; other fields default to empty /
 *   sensible defaults, with a banner telling the user to update them.
 *   When the backend adds GET /api/profile, replace the _loadProfile stub
 *   below with a real Api.getProfile() call.
 */
(function (global) {
  'use strict';

  // ── Toast ─────────────────────────────────────────────────────────────────────

  function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transition = 'opacity 0.3s';
      setTimeout(() => toast.remove(), 350);
    }, 3500);
  }

  function escapeHtml(str) {
    if (!str) return '';
    return str
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // ── Slider sync ───────────────────────────────────────────────────────────────

  function syncSlider(slider, display) {
    const val = parseInt(slider.value, 10);
    display.textContent = val;
    // Update CSS custom property for gradient fill
    const pct = ((val - 1) / 9) * 100;
    slider.style.setProperty('--val', pct + '%');
  }

  // ── Source checkboxes ─────────────────────────────────────────────────────────

  async function loadSourceCheckboxes(enabledSources) {
    const container = document.getElementById('sources-checkboxes');
    if (!container) return;

    try {
      const resp = await Api.getSources();
      container.innerHTML = '';

      resp.sources.forEach(src => {
        const isChecked = enabledSources.includes(src.source_id);
        const item = document.createElement('label');
        item.className = 'checkbox-item';
        item.innerHTML = `
          <input type="checkbox"
                 name="sources"
                 value="${escapeHtml(src.source_id)}"
                 ${isChecked ? 'checked' : ''}
                 ${!src.enabled ? 'disabled title="Not yet available"' : ''}>
          <span class="source-dot"
                style="background:${escapeHtml(src.color || '#555')}"></span>
          ${escapeHtml(src.display_name)}
          ${!src.enabled ? ' <em style="font-size:0.78rem;color:var(--gray-500)">(coming soon)</em>' : ''}
        `;
        container.appendChild(item);
      });
    } catch (err) {
      container.innerHTML = `<p class="form-error show">${escapeHtml(err.message)}</p>`;
    }
  }

  // ── Pre-fill ──────────────────────────────────────────────────────────────────

  /**
   * Stub: pre-fills from token only. Replace with Api.getProfile() once the
   * backend exposes GET /api/profile.
   */
  async function prefillForm(user) {
    const nameEl = document.getElementById('field-name');
    if (nameEl && user.name) nameEl.value = user.name;

    // Default enabled sources from token (not available without GET /profile)
    // Load checkboxes with afdb checked by default as a sensible fallback
    await loadSourceCheckboxes(['afdb']);

    // Sync slider initial display
    const slider  = document.getElementById('field-threshold');
    const display = document.getElementById('threshold-display');
    if (slider && display) syncSlider(slider, display);
  }

  // ── Collect form data ─────────────────────────────────────────────────────────

  function collectFormData() {
    const name = document.getElementById('field-name').value.trim();
    const profileText = document.getElementById('field-profile-text').value.trim();
    const threshold = parseInt(document.getElementById('field-threshold').value, 10);
    const notifEmail = document.getElementById('field-notification-email').value.trim();

    const sourceBoxes = document.querySelectorAll('input[name="sources"]:checked:not(:disabled)');
    const enabledSources = Array.from(sourceBoxes).map(cb => cb.value);

    return { name, profileText, threshold, enabledSources, notifEmail };
  }

  // ── Validate ──────────────────────────────────────────────────────────────────

  function validate(data) {
    const errors = [];
    if (!data.name) errors.push('Name is required.');
    if (data.profileText && data.profileText.length < 20) {
      errors.push('Career profile must be at least 20 characters.');
    }
    if (data.enabledSources.length === 0) {
      errors.push('Enable at least one job source.');
    }
    return errors;
  }

  // ── Save ──────────────────────────────────────────────────────────────────────

  async function onSave(e) {
    e.preventDefault();
    const errorEl = document.getElementById('form-error');
    errorEl.classList.remove('show');
    errorEl.textContent = '';

    const data = collectFormData();
    const errors = validate(data);
    if (errors.length) {
      errorEl.textContent = errors.join(' ');
      errorEl.classList.add('show');
      return;
    }

    const saveBtn = document.getElementById('btn-save');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    const payload = { name: data.name, enabled_sources: data.enabledSources, score_threshold: data.threshold };
    if (data.profileText) payload.profile_text = data.profileText;
    if (data.notifEmail)  payload.notification_email = data.notifEmail;

    try {
      await Api.updateProfile(payload);
      showToast('Profile saved successfully.', 'success');
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.classList.add('show');
      showToast('Save failed: ' + err.message, 'error');
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = 'Save Changes';
    }
  }

  // ── Init ──────────────────────────────────────────────────────────────────────

  async function init() {
    const user = Auth.requireAuth();
    if (!user) return;

    // Nav
    const navUser   = document.getElementById('nav-user');
    const navLogout = document.getElementById('btn-logout');
    if (navUser)   navUser.textContent = user.name;
    if (navLogout) navLogout.addEventListener('click', (e) => { e.preventDefault(); Auth.logout(); });

    // Pre-fill form
    await prefillForm(user);

    // Slider live update
    const slider  = document.getElementById('field-threshold');
    const display = document.getElementById('threshold-display');
    if (slider && display) {
      slider.addEventListener('input', () => syncSlider(slider, display));
    }

    // Profile text char counter
    const textarea    = document.getElementById('field-profile-text');
    const charCounter = document.getElementById('char-counter');
    if (textarea && charCounter) {
      textarea.addEventListener('input', () => {
        const len = textarea.value.length;
        charCounter.textContent = `${len} characters`;
        charCounter.className   = len >= 20 ? 'form-hint ok' : 'form-hint warn';
      });
    }

    // Form submit
    const form = document.getElementById('profile-form');
    if (form) form.addEventListener('submit', onSave);
  }

  document.addEventListener('DOMContentLoaded', init);

})(window);
