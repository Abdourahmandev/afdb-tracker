# GitHub Actions Secrets and Variables — Setup Guide

This is a one-time manual configuration performed in the GitHub repository settings
after the Azure infrastructure has been deployed. Estimated time: 10 minutes.

Target repository: **https://github.com/Abdourahmandev/afdb-tracker**
Target branch: **DEV**

---

## Why these are needed

Two GitHub Actions workflows gate all deployments:

| Workflow | File | Trigger |
|---|---|---|
| Deploy — Static Web App (DEV) | `.github/workflows/deploy-swa.yml` | Push to `DEV` touching `frontend/**` |
| Deploy — Azure Functions API (DEV) | `.github/workflows/deploy-api.yml` | Push to `DEV` touching `api/**`, `src/**`, `scrapers/**`, `requirements.txt` |

Both workflows pull credentials from repository secrets and variables at runtime.
No credentials are stored in code or `.env` files.

---

## Step 1 — Navigate to the secrets page

Open:

```
https://github.com/Abdourahmandev/afdb-tracker/settings/secrets/actions
```

You must be a repository admin or owner to access this page.

---

## Step 2 — Create repository secrets

Click **New repository secret** for each entry below.

### Secret 1 of 2 — SWA deployment token

| Field | Value |
|---|---|
| **Name** | `AZURE_STATIC_WEB_APPS_API_TOKEN_DEV` |
| **Secret** | See value below |

```
ff53d81d9c63548f557f1d1c8e834bcb7251286a55bc6c3c3a113096d2aca7b206-be6fa1b9-1781-40a8-9554-7da9897840cb00f27100f880790f
```

This token authorizes the `Azure/static-web-apps-deploy@v1` action to push
content to `swa-afdb-dev`. It was retrieved from:

```bash
MSYS_NO_PATHCONV=1 az staticwebapp secrets list \
  --name swa-afdb-dev \
  --resource-group rg-afdb-dev \
  --query "properties.apiKey" -o tsv
```

If you need to rotate it, run the command above again after a token reset.

---

### Secret 2 of 2 — Azure Functions publish profile

| Field | Value |
|---|---|
| **Name** | `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` |
| **Secret** | Full XML publish profile (see instructions below) |

**How to obtain the publish profile XML:**

Option A — Azure CLI (Git Bash on Windows):

```bash
MSYS_NO_PATHCONV=1 az webapp deployment list-publishing-profiles \
  --name func-afdb-dev \
  --resource-group rg-afdb-dev \
  --xml
```

Copy the entire XML output (starts with `<publishData>`, ends with `</publishData>`)
and paste it as the secret value.

Option B — Azure Portal:

1. Go to https://portal.azure.com
2. Open resource group `rg-afdb-dev`
3. Open the Function App `func-afdb-dev`
4. Click **Overview** in the left menu
5. Click **Get publish profile** (button in the top toolbar)
6. A `.PublishSettings` file downloads — open it in a text editor
7. Copy the entire XML content and paste it as the secret value

---

## Step 3 — Create repository variables

Still on the same page, click the **Variables** tab (next to Secrets), then
click **New repository variable** for the entry below.

### Variable 1 of 1 — Function App name

| Field | Value |
|---|---|
| **Name** | `AZURE_FUNCTION_APP_NAME` |
| **Value** | `func-afdb-dev` |

This is not a secret — it is a plain configuration value that tells the
`Azure/functions-action@v1` step which Function App to deploy to.

---

## Step 4 — Verify secrets are registered

After creating all entries the **Actions secrets and variables** page should show:

**Secrets**
- `AZURE_STATIC_WEB_APPS_API_TOKEN_DEV`
- `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`

**Variables**
- `AZURE_FUNCTION_APP_NAME`

> Note: secret values are never shown after creation. You can only update or
> delete them. If you made a typo, delete and recreate the secret.

---

## Step 5 — Trigger a test deployment

### Test the SWA pipeline

Make a trivial change to any file under `frontend/` and push to `DEV`:

```bash
# From repo root
echo " " >> frontend/index.html
git add frontend/index.html
git commit -m "chore: trigger SWA deploy test"
git push origin DEV
```

Then watch:
```
https://github.com/Abdourahmandev/afdb-tracker/actions
```

The **Deploy — Static Web App (DEV)** workflow should start, complete in ~1 minute,
and the site should be live at:

```
https://thankful-meadow-0f880790f.6.azurestaticapps.net
```

### Test the API pipeline

Make a trivial change to any file under `api/` or `src/` and push to `DEV`.
The **Deploy — Azure Functions API (DEV)** workflow will run tests first — the
deploy step only executes if tests pass.

```bash
# From repo root
echo "# test trigger" >> api/__init__.py
git add api/__init__.py
git commit -m "chore: trigger API deploy test"
git push origin DEV
```

---

## Deployment trigger reference

| What changed in the push | Workflow triggered | Deploy target |
|---|---|---|
| `frontend/**` | `deploy-swa.yml` | `swa-afdb-dev` → `https://thankful-meadow-0f880790f.6.azurestaticapps.net` |
| `api/**` | `deploy-api.yml` | `func-afdb-dev` → `https://func-afdb-dev.azurewebsites.net` |
| `src/**` | `deploy-api.yml` | `func-afdb-dev` → `https://func-afdb-dev.azurewebsites.net` |
| `scrapers/**` | `deploy-api.yml` | `func-afdb-dev` → `https://func-afdb-dev.azurewebsites.net` |
| `requirements.txt` | `deploy-api.yml` | `func-afdb-dev` → `https://func-afdb-dev.azurewebsites.net` |
| Any other path | (none — no workflow triggered) | — |

The API workflow has a hard gate: the `deploy` job has `needs: [test]`.
If `pytest` fails, deployment is blocked automatically.

---

## Security notes

- `AZURE_STATIC_WEB_APPS_API_TOKEN_DEV` is scoped to `swa-afdb-dev` only.
  Rotating it does not affect any other resource.
- `AZURE_FUNCTIONAPP_PUBLISH_PROFILE` grants deployment rights to `func-afdb-dev`.
  It does not grant any data-plane access to Cosmos DB or Key Vault — those use
  Managed Identity assigned via Bicep.
- Neither secret grants access to the Azure subscription itself. The service
  principal credential (`AZURE_CREDENTIALS`) used for infrastructure deployments
  is a separate, independent secret — add it only when running Bicep deployments
  from CI.
- `.env` files are for local development only. They are in `.gitignore` and must
  never be committed or included in container images.

---

## Troubleshooting

### SWA deploy fails: "Deployment token is invalid"

The token stored in the secret does not match the current token on `swa-afdb-dev`.
Retrieve the current token and update the secret:

```bash
MSYS_NO_PATHCONV=1 az staticwebapp secrets list \
  --name swa-afdb-dev \
  --resource-group rg-afdb-dev \
  --query "properties.apiKey" -o tsv
```

### Functions deploy fails: "Publish profile credentials are invalid"

The Function App's publish credentials may have been reset. Download a fresh
publish profile (Step 2, Secret 2 of 2) and update the secret.

### Tests fail in CI but pass locally

Check that `SKIP_AUTH=true` is set in the test job's `env:` block in
`deploy-api.yml`. The auth middleware has a mock path gated on this variable —
without it the tests attempt a live Entra token validation and fail in CI.

### Workflow does not trigger on push

Confirm the changed files match the `paths:` filter in the workflow file.
Only paths listed under `paths:` trigger the workflow. Infrastructure changes
under `infrastructure/` do not trigger either workflow by design.
