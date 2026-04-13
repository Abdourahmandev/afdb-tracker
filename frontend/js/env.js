/**
 * env.js — Runtime environment configuration for AfDB-Platform frontend.
 *
 * Sets the Entra External ID MSAL configuration values as window globals
 * so that auth.js can pick them up without a build step.
 *
 * Load this script BEFORE auth.js on every page.
 *
 * These are public client-side values (not secrets):
 *   - ENTRA_CLIENT_ID  : SPA application (client) ID from Entra External ID
 *   - ENTRA_AUTHORITY  : CIAM authority URL for the dev tenant
 *   - ENTRA_SCOPES     : comma-separated scope URI(s) requested when acquiring tokens
 */
(function (w) {
  // SPA (frontend) Application (client) ID — AfDB Platform SPA app registration
  w.ENTRA_CLIENT_ID = '12a8eca6-bfc7-44ad-b2e2-319623afdef7';

  // CIAM authority: https://<domain>.ciamlogin.com/<tenantId>
  w.ENTRA_AUTHORITY = 'https://afdbplatformdev.ciamlogin.com/af52e26b-cb95-4ffe-ab05-a95b73e09ada';

  // API scope — must match the scope exposed by the AfDB Platform API app registration
  // Format: api://<API_CLIENT_ID>/<scope_name>
  w.ENTRA_SCOPES = 'api://5958c7ab-9222-4621-9ac0-d094a720b1dc/jobs.read';
})(window);
