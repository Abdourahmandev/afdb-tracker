/**
 * api.js — API client for AfDB-Platform.
 *
 * All functions return parsed JSON or throw an Error whose message comes from
 * the API response body.
 *
 * Auth header is added automatically for authenticated endpoints.
 * Register, verifyEmail, and getSources are public (no auth header required).
 *
 * Exported as window.Api.
 */
(function (global) {
  'use strict';

  // Base URL: override via a <script> tag that sets window.API_BASE before
  // this file is loaded, or leave blank to use relative /api paths (correct
  // for both Static Web Apps proxy and local dev with a CORS-enabled backend).
  const API_BASE = global.API_BASE || '/api';

  // ── Internal helpers ─────────────────────────────────────────────────────────

  async function _authHeaders() {
    const token = await Auth.getToken();
    return {
      'Content-Type':  'application/json',
      'Authorization': `Bearer ${token}`,
    };
  }

  const _publicHeaders = {
    'Content-Type': 'application/json',
  };

  /**
   * Core fetch wrapper. Parses JSON response; on non-2xx status, throws
   * an Error with the API's `detail` message (FastAPI convention) or a
   * generic HTTP error string.
   */
  async function _fetch(url, options) {
    let response;
    try {
      response = await fetch(url, options);
    } catch (networkErr) {
      throw new Error(`Network error: ${networkErr.message}`);
    }

    // Parse body regardless of status so we can surface API error messages
    let body = null;
    const contentType = response.headers.get('content-type') || '';
    if (contentType.includes('application/json')) {
      try { body = await response.json(); } catch (_) { /* empty */ }
    } else {
      body = await response.text();
    }

    if (!response.ok) {
      const detail = (body && body.detail)
        ? (Array.isArray(body.detail) ? body.detail.map(e => e.msg).join('; ') : body.detail)
        : `HTTP ${response.status} ${response.statusText}`;
      throw new Error(detail);
    }

    return body;
  }

  // ── Public endpoints (no auth required) ──────────────────────────────────────

  /**
   * POST /api/register
   * @param {{ email: string, name: string, profile_text: string,
   *            score_threshold: number, enabled_sources: string[] }} data
   * @returns {Promise<{ message: string, user_id: string }>}
   */
  async function register(data) {
    // Attempt to include the Entra auth token so the backend can use the sub
    // claim as user_id, linking the profile to the Entra identity from day one.
    let headers = { ..._publicHeaders };
    try {
      const token = await Auth.getToken();
      if (token) headers['Authorization'] = `Bearer ${token}`;
    } catch (_) { /* not yet authenticated — register without token */ }
    return _fetch(`${API_BASE}/register`, {
      method:  'POST',
      headers,
      body:    JSON.stringify(data),
    });
  }

  /**
   * GET /api/verify?token=...
   * @param {string} token
   * @returns {Promise<{ message: string }>}
   */
  async function verifyEmail(token) {
    return _fetch(`${API_BASE}/verify?token=${encodeURIComponent(token)}`);
  }

  /**
   * GET /api/sources
   * @returns {Promise<{ sources: Array<{ source_id, display_name, enabled,
   *                                      color, enabled_by_default }> }>}
   */
  async function getSources() {
    return _fetch(`${API_BASE}/sources`);
  }

  // ── Authenticated endpoints ───────────────────────────────────────────────────

  /**
   * GET /api/jobs
   * @param {{ source?: string, min_score?: number, page?: number,
   *            limit?: number }} params
   * @returns {Promise<{ jobs: JobItem[], total: number, page: number,
   *                     limit: number }>}
   */
  async function getJobs(params = {}) {
    const qs = new URLSearchParams();
    if (params.source    != null) qs.set('source',    params.source);
    if (params.min_score != null) qs.set('min_score', params.min_score);
    if (params.page      != null) qs.set('page',      params.page);
    if (params.limit     != null) qs.set('limit',     params.limit);

    const qStr = qs.toString();
    const url  = `${API_BASE}/jobs${qStr ? '?' + qStr : ''}`;
    return _fetch(url, { headers: await _authHeaders() });
  }

  /**
   * GET /api/profile
   * @returns {Promise<UserProfile>}
   */
  async function getProfile() {
    return _fetch(`${API_BASE}/profile`, { headers: await _authHeaders() });
  }

  /**
   * PUT /api/profile
   * @param {{ name?: string, profile_text?: string, score_threshold?: number,
   *            enabled_sources?: string[], notification_email?: string }} data
   * @returns {Promise<UserProfile>}
   */
  async function updateProfile(data) {
    return _fetch(`${API_BASE}/profile`, {
      method:  'PUT',
      headers: await _authHeaders(),
      body:    JSON.stringify(data),
    });
  }

  /**
   * GET /api/health
   * @returns {Promise<{ status: string, version: string }>}
   */
  async function health() {
    return _fetch(`${API_BASE}/health`);
  }

  // ── Export ───────────────────────────────────────────────────────────────────

  global.Api = {
    register,
    verifyEmail,
    getSources,
    getJobs,
    getProfile,
    updateProfile,
    health,
  };

})(window);
