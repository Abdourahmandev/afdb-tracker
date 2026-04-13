/**
 * auth.js — Authentication module for AfDB-Platform frontend.
 *
 * Dev mode  (localhost / 127.0.0.1): skips MSAL entirely, returns a
 *   synthetic user with token "dev-token" (matches SKIP_AUTH=true on the
 *   backend).
 *
 * Prod mode: delegates to MSAL.js (loaded via CDN on pages that need auth).
 *   Tokens are kept in sessionStorage, never localStorage.
 *
 * Exported as window.Auth.
 */
(function (global) {
  'use strict';

  // ── Constants ────────────────────────────────────────────────────────────────

  const DEV_USER = {
    name:  'Dev User',
    email: 'dev@example.com',
    token: 'dev-token',
  };

  // MSAL configuration — populated from env at deploy time or from constants.
  // In prod, these values come from Azure Static Web Apps application settings
  // injected at build time (see deploy pipeline).
  const MSAL_CONFIG = {
    auth: {
      clientId:         global.ENTRA_CLIENT_ID  || '',
      authority:        global.ENTRA_AUTHORITY  || '',
      knownAuthorities: ['afdbplatformdev.ciamlogin.com'], // required: CIAM domain not in MSAL default trust list
      redirectUri: global.location && global.location.origin
                    ? global.location.origin + '/login.html'
                    : '',
      postLogoutRedirectUri: global.location ? global.location.origin : '',
    },
    cache: {
      cacheLocation:           'sessionStorage',  // never localStorage
      storeAuthStateInCookie:  false,
    },
  };

  const SCOPES = global.ENTRA_SCOPES
    ? global.ENTRA_SCOPES.split(',')
    : ['openid', 'profile', 'email'];

  // ── Helpers ──────────────────────────────────────────────────────────────────

  function isDev() {
    const h = global.location ? global.location.hostname : '';
    return h === 'localhost' || h === '127.0.0.1' || h === '';
  }

  let _msalInstance = null;

  function getMsalInstance() {
    if (_msalInstance) return _msalInstance;
    if (!global.msal) {
      console.error('auth.js: MSAL library not loaded. Include the CDN script before auth.js.');
      return null;
    }
    _msalInstance = new global.msal.PublicClientApplication(MSAL_CONFIG);
    return _msalInstance;
  }

  // ── Public API ───────────────────────────────────────────────────────────────

  /**
   * Returns the current user object {name, email, token} or null if not
   * authenticated.
   */
  function getUser() {
    if (isDev()) return DEV_USER;

    const msalApp = getMsalInstance();
    if (!msalApp) return null;

    const accounts = msalApp.getAllAccounts();
    if (!accounts.length) return null;

    const acc = accounts[0];
    return {
      name:  acc.name  || acc.username || 'User',
      email: acc.username || '',
      token: null,  // token is fetched async via getToken()
    };
  }

  /**
   * Returns a Promise resolving to the Bearer token string, or 'dev-token'
   * in dev mode.
   */
  async function getToken() {
    if (isDev()) return 'dev-token';

    const msalApp = getMsalInstance();
    if (!msalApp) throw new Error('MSAL not initialised.');

    const accounts = msalApp.getAllAccounts();
    if (!accounts.length) return null;

    const request = { scopes: SCOPES, account: accounts[0] };

    try {
      const result = await msalApp.acquireTokenSilent(request);
      return result.accessToken;
    } catch (err) {
      // Silent refresh failed — trigger interactive login
      console.warn('auth.js: Silent token acquisition failed, redirecting to login.', err);
      await msalApp.acquireTokenRedirect(request);
      return null;
    }
  }

  /**
   * Initiates an MSAL login redirect (no-op stub in dev).
   */
  async function login() {
    if (isDev()) {
      global.location.href = 'dashboard.html';
      return;
    }
    const msalApp = getMsalInstance();
    if (!msalApp) return;
    try {
      await msalApp.loginRedirect({ scopes: SCOPES });
    } catch (err) {
      console.error('auth.js: loginRedirect failed:', err);
      alert('Sign-in could not start: ' + err.message);
    }
  }

  /**
   * Logs out the current user.
   */
  async function logout() {
    if (isDev()) {
      global.location.href = 'index.html';
      return;
    }
    const msalApp = getMsalInstance();
    if (!msalApp) return;
    const accounts = msalApp.getAllAccounts();
    if (accounts.length) {
      await msalApp.logoutRedirect({ account: accounts[0] });
    }
  }

  /**
   * Handles the MSAL redirect callback on the login.html page.
   * Call this once on page load for login.html.
   */
  async function handleRedirect() {
    if (isDev()) return;
    const msalApp = getMsalInstance();
    if (!msalApp) return;
    try {
      const result = await msalApp.handleRedirectPromise();
      if (result) {
        // Successful login — go to dashboard
        global.location.href = 'dashboard.html';
      }
    } catch (err) {
      console.error('auth.js: Redirect handling error:', err);
    }
  }

  /**
   * Guards a protected page. Call at the top of dashboard.js / profile.js.
   * Redirects to index.html if user is not authenticated.
   * Returns the user object if authenticated.
   */
  function requireAuth() {
    const user = getUser();
    if (!user) {
      global.location.href = 'index.html';
      return null;
    }
    return user;
  }

  // ── Export ───────────────────────────────────────────────────────────────────

  global.Auth = {
    getUser,
    getToken,
    login,
    logout,
    handleRedirect,
    requireAuth,
    isDev,
  };

})(window);
