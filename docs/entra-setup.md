# Entra External ID — One-Time Manual Setup Guide

This is a one-time manual configuration performed in Azure Portal after the
Bicep infrastructure has been deployed. Estimated time: 30 minutes.

Target environment: **dev** (repeat for qa/prod, substituting tenant and app names).

---

## 1. Create the Entra External ID Tenant

1. Sign in to [portal.azure.com](https://portal.azure.com) with the subscription owner account.
2. In the top search bar, type **Microsoft Entra External ID** and select it.
3. Click **Create a tenant**.
4. Under **Select a tenant type**, choose **External** (customer-facing apps, CIAM).
5. Fill in the form:
   - **Organization name**: `AfDB Platform Dev`
   - **Domain name**: `afdb-platform` → results in `afdb-platform.onmicrosoft.com`
   - **Country/Region**: choose your data-residency requirement
6. Click **Review + Create**, then **Create**.
7. Wait for provisioning (1–3 minutes), then click **Go to tenant**.
8. Note the **Tenant ID** shown in the Overview blade. You will need it in Step 6.

---

## 2. Register the SPA (Frontend)

1. Inside the new Entra External ID tenant, go to **App registrations** → **New registration**.
2. Fill in:
   - **Name**: `AfDB Platform SPA`
   - **Supported account types**: Accounts in this organizational directory only (single tenant)
   - **Platform**: Single-page application
   - **Redirect URIs**:
     - `http://localhost:3000` (local dev)
     - `https://<your-swa-hostname>.azurestaticapps.net` (replace with the value of `defaultHostname` output from the Bicep deploy)
3. Click **Register**.
4. On the app overview page, copy and save:
   - **Application (client) ID** — referred to as `SPA_CLIENT_ID` below
   - **Directory (tenant) ID** — same as the tenant ID from Step 1

> The SPA does **not** need a client secret. SPAs use the Authorization Code flow
> with PKCE, which does not require a secret.

---

## 3. Register the API (Backend)

1. Go to **App registrations** → **New registration**.
2. Fill in:
   - **Name**: `AfDB Platform API`
   - **Supported account types**: Accounts in this organizational directory only
   - **Redirect URI**: leave blank (APIs do not redirect)
3. Click **Register**.
4. On the app overview page, go to **Expose an API**.
5. Click **Add** next to **Application ID URI**. Accept the default
   `api://<API_CLIENT_ID>` or set a custom value. Click **Save**.
6. Click **Add a scope**:
   - **Scope name**: `jobs.read`
   - **Who can consent**: Admins and users
   - **Admin consent display name**: `Read job listings`
   - **Admin consent description**: `Allows the app to read evaluated job listings for the signed-in user.`
   - **State**: Enabled
7. Click **Add scope**.
8. Copy and save:
   - **Application ID URI** — e.g. `api://<API_CLIENT_ID>` — referred to as `API_APP_URI` below
   - **Application (client) ID** of the API app — referred to as `API_CLIENT_ID` below

---

## 4. Grant the SPA Access to the API Scope

1. Go back to the **AfDB Platform SPA** app registration.
2. Click **API permissions** → **Add a permission**.
3. Select **My APIs** tab → select **AfDB Platform API**.
4. Under **Delegated permissions**, check `jobs.read`.
5. Click **Add permissions**.
6. Click **Grant admin consent for AfDB Platform Dev** → **Yes**.
7. Verify the `jobs.read` permission row shows a green checkmark under **Status**.

---

## 5. Create User Flows

1. In the Entra External ID tenant, click **User flows** in the left menu.
2. Click **New user flow**.
3. Select **Sign up and sign in (recommended)**.
4. Configure:
   - **Name**: `signupsignin` → full name becomes `B2C_1_signupsignin`
   - **Identity providers**: check **Email + password**
   - **MFA**: Off (can enable later)
   - **User attributes to collect**: check **Display name** and **Email address**
   - **Claims to return in token**: check **Display name**, **Email addresses**, **User's Object ID**
5. Click **Create**.
6. Click **Run user flow** to open a browser test and verify the sign-up form loads.

---

## 6. Set Key Vault Secrets

After tenant creation is complete, store the Entra values as secrets in
**kv-afdb-dev** (already provisioned by Bicep). Run these from a shell
with `az` logged in as the Key Vault administrator:

```bash
# Substitute your actual values before running

KV="kv-afdb-dev"

az keyvault secret set --vault-name "$KV" \
  --name "EntraClientId" \
  --value "<SPA_CLIENT_ID>"

az keyvault secret set --vault-name "$KV" \
  --name "EntraTenantId" \
  --value "<TENANT_ID>"

az keyvault secret set --vault-name "$KV" \
  --name "EntraAuthority" \
  --value "https://afdb-platform.ciamlogin.com/afdb-platform.onmicrosoft.com"
```

Also update `infrastructure/main.parameters.dev.json` — replace the placeholder
values for `entraExternalTenantId` and `entraClientId` with the real IDs, then
re-run `./infrastructure/scripts/deploy.sh dev` to push the values into the
Function App's environment.

---

## 7. Update `api/auth.py` — Function App Environment Variables

In the Function App configuration (**func-afdb-dev** → Configuration →
Application settings), add or update these entries. Use Key Vault references
(`@Microsoft.KeyVault(SecretUri=...)`) rather than raw values:

| Setting name      | Value source                      | Example Key Vault ref                                          |
|-------------------|-----------------------------------|----------------------------------------------------------------|
| `ENTRA_TENANT_ID` | Secret `EntraTenantId` in kv-afdb-dev | `@Microsoft.KeyVault(VaultName=kv-afdb-dev;SecretName=EntraTenantId)` |
| `ENTRA_CLIENT_ID` | Secret `EntraClientId` in kv-afdb-dev (the **API** app's client ID) | `@Microsoft.KeyVault(VaultName=kv-afdb-dev;SecretName=EntraClientId)` |
| `ENTRA_AUTHORITY` | Secret `EntraAuthority` in kv-afdb-dev | `@Microsoft.KeyVault(VaultName=kv-afdb-dev;SecretName=EntraAuthority)` |

> `ENTRA_CLIENT_ID` here must be the **API app** (`AfDB Platform API`) client
> ID, not the SPA client ID. The API uses it to validate that incoming tokens
> were issued for the correct audience.

Click **Save** after adding all settings. The Function App will restart automatically.

---

## 8. Update `frontend/js/auth.js`

Once the tenant and SPA app registration exist, replace the placeholder values
in `frontend/js/auth.js`:

```js
const MSAL_CONFIG = {
  auth: {
    clientId: "YOUR_SPA_CLIENT_ID",       // <-- replace with SPA_CLIENT_ID from Step 2
    authority: "https://afdb-platform.ciamlogin.com/afdb-platform.onmicrosoft.com",
    redirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
};
```

The `authority` URL follows the CIAM pattern:
`https://<domain>.ciamlogin.com/<domain>.onmicrosoft.com`

The API scope string passed to `acquireTokenSilent` / `acquireTokenPopup` must
match the full scope URI from Step 3:

```js
const API_SCOPES = ["api://<API_CLIENT_ID>/jobs.read"];  // replace API_CLIENT_ID
```

Commit `frontend/js/auth.js` to the `DEV` branch — the `deploy-swa.yml`
workflow will pick it up automatically.

---

## Verification Checklist

- [ ] Navigating to the Static Web App URL redirects to the Entra External ID
      sign-up/sign-in page (user flow `B2C_1_signupsignin` loads correctly).
- [ ] A new test account can complete sign-up with email + password and receives
      a verification email.
- [ ] After sign-in, `GET /api/jobs` returns HTTP 200 with a valid Bearer token
      (confirm via browser DevTools → Network tab or Postman).
- [ ] Calling `GET /api/jobs` without a token returns HTTP 401 Unauthorized.
- [ ] Azure Key Vault secrets `EntraClientId`, `EntraTenantId`, and
      `EntraAuthority` are accessible by the Function App's Managed Identity
      (confirm in Key Vault → Access policies that `func-afdb-dev` principal has
      **Get** on secrets).
