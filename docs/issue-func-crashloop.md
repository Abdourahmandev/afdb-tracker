# Issue: func-afdb-dev Python worker crash-loops — 404 on all routes

**Repo:** Abdourahmandev/afdb-tracker  
**Labels:** `bug`, `deployment`, `sprint-4`

---

## Summary

After zip deployment, `func-afdb-dev` enters a crash loop. The Functions host container starts fine but the Python worker never registers functions — every request returns HTTP 404.

## Symptoms

- `curl https://func-afdb-dev.azurewebsites.net/api/health` → HTTP 404
- Docker log: container restart loop (image pulled every ~2 min)
- wwwroot contains all expected files: `function_app.py`, `api/`, `src/`, `.python_packages/`
- Kudu `/api/functions` returns `No route registered`

## Root Cause Candidates (ranked by likelihood)

1. **Python version mismatch** — `.python_packages/` was installed locally with Python 3.13 but the Azure Functions runtime uses Python 3.12. Binary wheels (`pydantic-core`, `cryptography`, etc.) are version-specific and crash the worker at import.

2. **Missing app settings** — `api/main.py` imports `cosmos_db` at module level. If `COSMOS_ENDPOINT` / `COSMOS_KEY` are not set, `CosmosClient` construction fails on import → worker exits.

3. **`SKIP_AUTH` / `DEV_USER_EMAIL` not set** — `api/auth.py` uses these env vars; missing values may cause import-time crash.

## Fix Plan

### Step 1 — Add missing app settings
```bash
MSYS_NO_PATHCONV=1 az functionapp config appsettings set \
  --name func-afdb-dev --resource-group rg-afdb-dev \
  --settings \
    SKIP_AUTH=true \
    DEV_USER_EMAIL=test@example.com \
    COSMOS_ENDPOINT=https://cosmos-afdb-dev.documents.azure.com:443/ \
    COSMOS_DATABASE=afdb-platform
```

### Step 2 — Enable remote build (server-side pip install with Python 3.12)
```bash
MSYS_NO_PATHCONV=1 az functionapp config appsettings set \
  --name func-afdb-dev --resource-group rg-afdb-dev \
  --settings \
    ENABLE_ORYX_BUILD=true \
    SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

### Step 3 — Rebuild zip WITHOUT .python_packages (let Azure install deps)
```powershell
$proj = 'C:\Users\User\Documents\BdeB Mathmatique\Pogrammation de pipeline de donnee\afdb_job_tracker'
$zip = "$proj\func-deploy.zip"
Remove-Item $zip -Force -ErrorAction SilentlyContinue
Add-Type -Assembly 'System.IO.Compression.FileSystem'
$z = [System.IO.Compression.ZipFile]::Open($zip, 'Create')
foreach ($file in @('function_app.py','host.json','requirements.txt')) {
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($z, "$proj\$file", $file) | Out-Null
}
foreach ($dir in @('api','src')) {
    Get-ChildItem "$proj\$dir" -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($proj.Length+1).Replace('\','/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($z, $_.FullName, $rel) | Out-Null
    }
}
$z.Dispose()
Write-Host "Done: $([math]::Round((Get-Item $zip).Length/1MB,1)) MB"
```

### Step 4 — Redeploy
```bash
MSYS_NO_PATHCONV=1 az functionapp deployment source config-zip \
  --name func-afdb-dev --resource-group rg-afdb-dev \
  --src func-deploy.zip --build-remote true --timeout 300
```

### Step 5 — Verify (allow ~3 min for remote build)
```bash
curl -s -w "\nHTTP %{http_code}" https://func-afdb-dev.azurewebsites.net/api/health --max-time 60
```
Expected: `{"status":"ok"}` with HTTP 200.

### Step 6 — If still 404, get the exact traceback via Kudu
```bash
CREDS="$func-afdb-dev:ZfgtPXqfLDFmJ75mp3Np7kNSPfSpLw3yjaXbeisoSxpNvjHu09b0g2f7ZNXd"
curl -s -X POST \
  "https://${CREDS}@func-afdb-dev.scm.azurewebsites.net/api/command" \
  -H "Content-Type: application/json" \
  -d '{"command":"cd /home/site/wwwroot && python3 function_app.py 2>&1 | head -40","dir":"/"}' 
```

## Acceptance Criteria

- [ ] `GET /api/health` returns `{"status":"ok"}` HTTP 200
- [ ] `GET /api/jobs` with `Authorization: Bearer dev-token` returns jobs list
- [ ] No crash loop in docker logs
