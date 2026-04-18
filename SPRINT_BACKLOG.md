# Sprint Backlog

## Sprint 0 — Foundation
**Goal**: Architecture, IaC skeleton, scraper config, and cost model. No production changes.  
**Branch**: `dev`  
**Status**: IN PROGRESS

---

### Deliverables Checklist

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| S0-01 | Create 5 subagent definition files in `.claude/agents/` | delivery-lead | ✅ Done | All 5 agents defined |
| S0-02 | Write ROADMAP.md (multi-source vision, 6 phases) | delivery-lead | ✅ Done | |
| S0-03 | Write SPRINT_BACKLOG.md (this file) | delivery-lead | ✅ Done | |
| S0-04 | Write living cost model (`docs/cost-model.md`) | arch-fin | ✅ Done | Cosmos DB free tier |
| S0-05 | Write ADR-001: Database choice | arch-fin | ✅ Done | Cosmos DB NoSQL |
| S0-06 | Write ADR-002: Auth provider | arch-fin | ✅ Done | Entra External ID |
| S0-07 | Create Bicep IaC skeleton (`infrastructure/`) | devops-sec | ✅ Done | 6 modules |
| S0-08 | Create `scrapers/` pluggable skeleton | backend-pipeline | ✅ Done | BaseScraper + sources.yaml |
| S0-09 | Document LEGACY_MODE flag in README | backend-pipeline | ✅ Done | |
| S0-10 | Remove obsolete files (kanban.md, agent-plan.md) | delivery-lead | ✅ Done | User approved |

---

### Sprint 0 Review Summary

**Date**: 2026-04-12

#### ✅ Completed
- **Team structure**: 5 subagent definitions live in `.claude/agents/` — delivery-lead, arch-fin, backend-pipeline, web-frontend, devops-sec
- **Vision documented**: ROADMAP.md covers 6 phases from Foundation → Scale, with architecture diagram and non-negotiables
- **Cost model**: `docs/cost-model.md` — full free-tier breakdown, $0–$2/month estimate for <50 users
- **ADRs**: ADR-001 (Cosmos DB) and ADR-002 (Entra External ID) written with cost impact and tradeoffs
- **IaC skeleton**: 6 Bicep modules in `infrastructure/` — Cosmos DB, Container Apps Job, Static Web Apps, Functions, Key Vault, Storage
- **Scraper skeleton**: `scrapers/base.py` + `scrapers/config/sources.yaml` + AfDB wrapper scaffold
- **Legacy protected**: `LEGACY_MODE` flag documented; existing `src/` files untouched

#### 🧪 What You Can Test Now

| Thing to test | How |
|---|---|
| Legacy pipeline still works | `docker build -t afdb-tracker . && docker run --env-file .env afdb-tracker` |
| Bicep validates | `az bicep build --file infrastructure/main.bicep` |
| Scraper config loads | `python -c "import yaml; print(yaml.safe_load(open('scrapers/config/sources.yaml')))"` |
| Cost model readable | Open `docs/cost-model.md` |
| Agent team structure | Review `.claude/agents/` — 5 `.md` files |

#### ⏭ Deferred to Sprint 1
- Cosmos DB Python client (`src/cosmos_db.py`)
- AfDB scraper wrapped into `BaseScraper`
- World Bank scraper (new source)
- Dual-mode pipeline implementation

#### 🎯 Sprint 1 Goal
Build the multi-tenant backend: Cosmos DB integration, AfDB+World Bank scrapers, per-user evaluation, dual-mode pipeline testable locally.

---

## Sprint 1 — Backend Core ✅ COMPLETE

| # | Task | Owner | Status | File |
|---|------|-------|--------|------|
| S1-01 | `src/cosmos_db.py` — Cosmos DB client, upsert patterns | backend-pipeline | ✅ Done | [src/cosmos_db.py](src/cosmos_db.py) |
| S1-02 | AfDB scraper wrapped in BaseScraper | backend-pipeline | ✅ Done (Sprint 0) | [scrapers/afdb/scraper.py](scrapers/afdb/scraper.py) |
| S1-03 | World Bank scraper | backend-pipeline | ✅ Placeholder | [scrapers/worldbank/scraper.py](scrapers/worldbank/scraper.py) |
| S1-04 | Dual-mode LEGACY_MODE flag in `src/main.py` | backend-pipeline | ✅ Done | [src/main.py](src/main.py) |
| S1-05 | `src/evaluator_v2.py` — per-user Gemini scoring | backend-pipeline | ✅ Done | [src/evaluator_v2.py](src/evaluator_v2.py) |
| S1-06 | `src/notifier_v2.py` — multi-user digest email | backend-pipeline | ✅ Done | [src/notifier_v2.py](src/notifier_v2.py) |
| S1-06b | `src/pipeline_v2.py` — multi-tenant orchestrator | backend-pipeline | ✅ Done | [src/pipeline_v2.py](src/pipeline_v2.py) |
| S1-07 | Cosmos DB Bicep module (Sprint 0) | devops-sec | ✅ Done | [infrastructure/modules/cosmosdb.bicep](infrastructure/modules/cosmosdb.bicep) |
| S1-08 | Cost model — free tier confirmed | arch-fin | ✅ Done | [docs/cost-model.md](docs/cost-model.md) |
| S1-09 | E2E tests: 2 users, correct evals + emails | backend-pipeline | ✅ Done | [tests/test_pipeline_v2.py](tests/test_pipeline_v2.py) |

### Sprint 1 Review Summary — 2026-04-12

#### ✅ Completed

| Deliverable | What it does |
|---|---|
| `src/cosmos_db.py` | Cosmos DB client: upsert jobs/users/evaluations, query by source, track email status |
| `src/evaluator_v2.py` | Per-user Gemini scoring using `user.profile_text` |
| `src/notifier_v2.py` | One digest email per user — all matched jobs with source + score badges |
| `src/pipeline_v2.py` | Multi-tenant orchestrator: scrape → upsert → evaluate per user → digest email |
| `src/main.py` (±6 lines) | `LEGACY_MODE=true` → original pipeline; `LEGACY_MODE=false` → pipeline_v2 |
| `src/scheduler.py` (±1 line) | Calls LEGACY_MODE-aware `run()` entry point |
| `tests/test_pipeline_v2.py` | 8 tests: evaluator, notifier, pipeline wiring, legacy guard |
| `requirements.txt` | Added: `azure-cosmos`, `azure-identity`, `pyyaml`, `pytest` |

#### 🧪 What You Can Test Now

| Test | Command |
|---|---|
| Legacy pipeline unchanged | `docker build -t afdb-tracker . && docker run --env-file .env afdb-tracker` |
| All unit tests (no cloud needed) | `pip install -r requirements.txt && python -m pytest tests/ -v` |
| LEGACY_MODE routing | `LEGACY_MODE=true python src/main.py` (calls original pipeline) |
| New pipeline locally | Add `COSMOS_CONNECTION_STRING` to `.env`, then `LEGACY_MODE=false python src/pipeline_v2.py` |

#### ⏭ Deferred to Sprint 2
- FastAPI API layer — /register, /verify, /jobs, /profile
- Entra External ID OIDC token validation
- Vector embeddings (Cosmos DB vector index) — scoring currently uses full Gemini
- Cosmos DB dev seed script

#### 🎯 Sprint 2 Goal
REST API deployable to Azure Functions dev: /register, /verify, /jobs, /profile with Entra External ID authentication.

---

## Sprint 2 — API Layer ✅ COMPLETE

| # | Task | Owner | Status | File |
|---|------|-------|--------|------|
| S2-01 | FastAPI app — Azure Functions v2 ASGI | backend-pipeline | ✅ Done | [api/main.py](api/main.py), [function_app.py](function_app.py), [host.json](host.json) |
| S2-02 | `POST /api/register` + verification email | backend-pipeline | ✅ Done | [api/main.py](api/main.py) |
| S2-03 | `GET /api/verify` — activate user | backend-pipeline | ✅ Done | [api/main.py](api/main.py) |
| S2-04 | `GET /api/jobs` — paginated + filtered | backend-pipeline | ✅ Done | [api/main.py](api/main.py) |
| S2-05 | `PUT /api/profile` — update preferences | backend-pipeline | ✅ Done | [api/main.py](api/main.py) |
| S2-06 | `GET /api/sources` from sources.yaml | backend-pipeline | ✅ Done | [api/main.py](api/main.py) |
| S2-07 | Entra External ID JWT validation + SKIP_AUTH dev mode | backend-pipeline | ✅ Done | [api/auth.py](api/auth.py) |
| S2-08 | Deploy to Azure Functions — Bicep already done Sprint 0 | devops-sec | ✅ Ready | [infrastructure/modules/functions.bicep](infrastructure/modules/functions.bicep) |
| S2-09 | Cosmos DB dev seed script | backend-pipeline | ✅ Done | [scripts/seed_cosmos.py](scripts/seed_cosmos.py) |
| S2-10 | API integration tests (16 tests, all mocked) | backend-pipeline | ✅ Done | [tests/test_api.py](tests/test_api.py) |

### Sprint 2 Review Summary — 2026-04-12

#### ✅ Completed

| Deliverable | What it does |
|---|---|
| `api/main.py` | FastAPI app: 5 endpoints + CORS + health check |
| `api/auth.py` | Entra External ID JWT validation; `SKIP_AUTH=true` bypasses for local dev |
| `api/models.py` | Pydantic v2 request/response models for all endpoints |
| `function_app.py` | Azure Functions v2 ASGI wrapper — one file, zero config |
| `host.json` | Azure Functions host config (v4 extension bundle) |
| `scripts/seed_cosmos.py` | Seeds 2 test users + 3 sample jobs into Cosmos DB |
| `src/cosmos_db.py` (+3 fns) | Added `get_user_by_email`, `get_user_by_id`, `get_user_by_verification_token` |
| `tests/test_api.py` | 16 tests: all endpoints, auth bypass, error cases |
| `requirements.txt` | Added: fastapi, pydantic[email], uvicorn, azure-functions, PyJWT[crypto], httpx |

#### 🧪 What You Can Test Now

| Test | Command |
|---|---|
| All tests (no cloud) | `pip install -r requirements.txt && python -m pytest tests/ -v` |
| FastAPI dev server | `SKIP_AUTH=true uvicorn api.main:app --reload --port 7071` |
| Swagger UI | Open `http://localhost:7071/docs` after starting dev server |
| Health check | `curl http://localhost:7071/api/health` |
| List sources | `curl http://localhost:7071/api/sources` |
| Register a user | `curl -X POST http://localhost:7071/api/register -H "Content-Type: application/json" -d '{"email":"test@example.com","name":"Test","profile_text":"Data engineer with 5+ years Python SQL Azure experience in analytics.","score_threshold":7,"enabled_sources":["afdb"]}'` |
| Seed Cosmos DB | Set `COSMOS_CONNECTION_STRING` in `.env`, then `python scripts/seed_cosmos.py` |

#### ⏭ Deferred to Sprint 3
- Azure Functions deployment to dev Azure environment (needs Entra tenant configured)
- Entra External ID tenant setup (manual one-time step in Azure Portal)
- Frontend (Sprint 3)

#### 🎯 Sprint 3 Goal
Build the web frontend on Azure Static Web Apps: landing page, MSAL login, registration wizard, unified job dashboard, profile editor.

---

## Sprint 3 — Frontend ✅ COMPLETE

| # | Task | Owner | Status | File |
|---|------|-------|--------|------|
| S3-01 | `frontend/` folder structure + `staticwebapp.config.json` | web-frontend | ✅ Done | [frontend/staticwebapp.config.json](frontend/staticwebapp.config.json) |
| S3-02 | Landing page (`index.html`) with login button | web-frontend | ✅ Done | [frontend/index.html](frontend/index.html) |
| S3-03 | MSAL.js auth module (`frontend/js/auth.js`) | web-frontend | ✅ Done | [frontend/js/auth.js](frontend/js/auth.js) |
| S3-04 | Registration wizard — email → verify → profile setup | web-frontend | ✅ Done | [frontend/register.html](frontend/register.html) |
| S3-05 | Job dashboard (`dashboard.html`) — multi-source, filterable, sortable | web-frontend | ✅ Done | [frontend/dashboard.html](frontend/dashboard.html) |
| S3-06 | Profile editor (`profile.html`) — career text, source toggles, score slider | web-frontend | ✅ Done | [frontend/profile.html](frontend/profile.html) |
| S3-07 | API client module (`frontend/js/api.js`) — fetch wrappers with auth headers | web-frontend | ✅ Done | [frontend/js/api.js](frontend/js/api.js) |
| S3-08 | Source + score badges (color-coded) | web-frontend | ✅ Done | [frontend/css/main.css](frontend/css/main.css) |
| S3-09 | GitHub Actions CI/CD workflows (SWA + API) | devops-sec | ✅ Done | [.github/workflows/](/.github/workflows/) |
| S3-10 | Entra External ID setup guide | devops-sec | ✅ Done | [docs/entra-setup.md](docs/entra-setup.md) |
| S3-11 | API bug fixes (min_score filter, scraper awaitable, CORS) | backend-pipeline | ✅ Done | [api/main.py](api/main.py), [src/pipeline_v2.py](src/pipeline_v2.py) |

### Sprint 3 Review Summary — 2026-04-12

#### ✅ Completed

| Deliverable | What it does |
|---|---|
| `frontend/index.html` | Landing page: hero, Sign In (MSAL), Register button; auto-redirect if authenticated |
| `frontend/register.html` | 3-step wizard: email+name → career profile text → score threshold + source checkboxes |
| `frontend/dashboard.html` | Job grid: source/score filter bar, color-coded badges, 25-per-page pagination |
| `frontend/profile.html` | Profile editor: name, profile text, score slider, source toggles, notification email |
| `frontend/login.html` | MSAL redirect handler; dev-mode no-op fallback |
| `frontend/css/main.css` | CSS variables, card grid, source badges (afdb=#003366, worldbank=#009FDA, undp=#1C9D4B, imf=#cc2233), score badges |
| `frontend/js/auth.js` | Dev-mode: returns fake token + user (matches SKIP_AUTH=true); prod: MSAL.js flows |
| `frontend/js/api.js` | Fetch wrappers for all 5 endpoints; auto-injects Bearer token; readable 422 errors |
| `frontend/js/dashboard.js` | Source filter, min_score filter, debounced reload, pagination, dynamic card rendering |
| `frontend/js/profile.js` | Form pre-fill (name from token), save → PUT /api/profile, success toast |
| `.github/workflows/deploy-swa.yml` | SWA deploy on push to DEV `frontend/**`; close-PR cleanup job |
| `.github/workflows/deploy-api.yml` | API deploy: tests gate deploy (separate jobs); SKIP_AUTH scoped to test step only |
| `docs/entra-setup.md` | Step-by-step Entra External ID tenant + app registrations + Key Vault secrets |
| `api/main.py` (fix) | `min_score` filter now excludes unscored jobs; CORS updated for SWA wildcard + localhost:7071 |
| `src/pipeline_v2.py` (fix) | `inspect.isawaitable()` — handles both async scrapers and sync mocks correctly |

#### 🧪 What You Can Test Now

| Test | Command / Action |
|---|---|
| All 23 unit tests | `pip install -r requirements.txt && python -m pytest tests/ -v` |
| FastAPI dev server | `SKIP_AUTH=true uvicorn api.main:app --reload --port 7071` |
| Frontend locally | Open `frontend/index.html` in browser (or `npx serve frontend` on port 3000) |
| Registration flow | Open `frontend/register.html` → fill 3 steps → POST hits `http://localhost:7071/api/register` |
| Dashboard | Open `frontend/dashboard.html` → loads jobs from `http://localhost:7071/api/jobs` |
| Profile editor | Open `frontend/profile.html` → edit fields → PUT hits `/api/profile` |

#### ⚠️ Known Limitations / Deferred

| Item | Note |
|---|---|
| `GET /api/profile` endpoint missing | `profile.js` pre-fills name from token only; add `GET /api/profile` in Sprint 4 to populate all fields |
| `%%BACKEND_URL%%` placeholder in `staticwebapp.config.json` | CI/CD `sed` replacement needed before SWA deploy — covered in `deploy-swa.yml` comments |
| Entra External ID tenant | Manual one-time setup required — follow `docs/entra-setup.md` |
| SWA + API GitHub secrets | `AZURE_STATIC_WEB_APPS_API_TOKEN_DEV`, `AZURE_FUNCTIONAPP_PUBLISH_PROFILE`, `AZURE_FUNCTION_APP_NAME` var must be set before pipelines go live |

#### ⏭ Deferred to Sprint 4

- Azure deployment to dev environment (needs Entra tenant + GitHub secrets configured)
- `GET /api/profile` endpoint
- Vector embeddings / Cosmos DB vector index (scoring shortlist)
- World Bank scraper real implementation
- End-to-end test with real Cosmos DB (seed script → API → dashboard)

#### 🎯 Sprint 4 Goal
Deploy to Azure dev environment: provision resources via Bicep, configure Entra External ID, set GitHub secrets, and run a full end-to-end test from registration through job dashboard.

---

## Sprint 4 — Infrastructure & CI/CD + Full Dev Deployment ✅ COMPLETE

**Goal**: All Azure resources live, API and SWA deployed to dev, Entra login working end-to-end, real user data in Cosmos DB.
**Branch**: `dev`
**Status**: COMPLETE

### Deliverables Checklist

| # | Task | Owner | Status | Notes |
|---|------|-------|--------|-------|
| S4-01 | All 8 Azure resources provisioned (`rg-afdb-dev`, australiacentral) | devops-sec | ✅ Done | Cosmos DB, Function App, SWA, Key Vault, Container Registry, Storage |
| S4-02 | API live: `func-afdb-dev` GET /api/health returns 200 | devops-sec | ✅ Done | |
| S4-03 | GET /api/jobs returns real scored results | backend-pipeline | ✅ Done | 43 AfDB jobs live |
| S4-04 | GET /api/profile endpoint added and confirmed working | backend-pipeline | ✅ Done | Returns email, name, score_threshold, enabled_sources |
| S4-05 | GET /api/sources returns 4 sources (afdb, worldbank, undp, imf) | backend-pipeline | ✅ Done | sources.yaml bundled in deploy zip |
| S4-06 | Cosmos DB seeded: 43 real AfDB jobs + 43 evaluations migrated from DuckDB | backend-pipeline | ✅ Done | `scripts/migrate_duckdb_to_cosmos.py` |
| S4-07 | SWA deployed at https://thankful-meadow-0f880790f.6.azurestaticapps.net | devops-sec | ✅ Done | Fully working |
| S4-08 | Entra External ID tenant configured; MSAL login flow working end-to-end | devops-sec | ✅ Done | login → token → dashboard confirmed |
| S4-09 | GitHub Actions CI/CD: deploy-swa.yml + deploy-api.yml green and auto-deploying | devops-sec | ✅ Done | Both pipelines green on push to DEV |
| S4-10 | KV role assignment: Function App managed identity has Key Vault Secrets User role | devops-sec | ✅ Done | Manual assignment; secrets confirmed loading |
| S4-11 | DEV_USER_ID + DEV_USER_EMAIL env vars so SKIP_AUTH=true uses real Cosmos DB user | backend-pipeline | ✅ Done | `api/auth.py` updated |
| S4-12 | `scripts/backfill_empty_jobs.py`: recovered titles/locations for 8/10 empty-metadata jobs | backend-pipeline | ✅ Done | 2 jobs expired on AfDB site, show "Position Closed" |
| S4-13 | `frontend/js/dashboard.js`: "Position Closed" fallback for expired jobs | web-frontend | ✅ Done | |
| S4-14 | `frontend/js/env.js` (new): runtime Entra config injected before auth.js on every page | web-frontend | ✅ Done | |
| S4-15 | MSAL CDN switched to jsDelivr; correct SRI hash; knownAuthorities + scope split | web-frontend | ✅ Done | Was silently failing with alcdn.msauth.net CDN |
| S4-16 | `staticwebapp.config.json`: removed allowedRoles SWA route restrictions | web-frontend | ✅ Done | Conflicted with MSAL client-side auth |
| S4-17 | `kv-roles.bicep` Bicep idempotency fix | devops-sec | ⏭ Deferred | Role works via manual assignment; carry to Sprint 5 |
| S4-18 | `profile.js` → GET /api/profile pre-fill all fields on page load | web-frontend | ⏭ Deferred | Endpoint exists; save/update flow works; carry to Sprint 5 |

---

### Sprint 4 Review Summary — 2026-04-13

#### Completed

| Deliverable | What it does |
|---|---|
| All 8 Azure resources (rg-afdb-dev) | Cosmos DB, Function App, SWA, Key Vault, Container Registry, Storage all provisioned in australiacentral |
| `func-afdb-dev` API | GET /api/health 200, GET /api/jobs (43 real jobs), GET /api/profile, GET /api/sources all live |
| `scripts/migrate_duckdb_to_cosmos.py` | Migrated 43 real AfDB jobs + 43 evaluations from DuckDB into Cosmos DB |
| `scripts/backfill_empty_jobs.py` | Recovered titles/locations for 8/10 jobs that had empty metadata from original DuckDB scrape |
| SWA at https://thankful-meadow-0f880790f.6.azurestaticapps.net | Fully deployed and serving the dashboard, login, and profile pages |
| Entra External ID MSAL login flow | Tenant configured, CIAM knownAuthorities set, LOGIN_SCOPES/TOKEN_SCOPES split; login → token → dashboard confirmed |
| `frontend/js/env.js` | Runtime Entra config (clientId, tenantId, redirectUri) injected on every page; no build step required |
| `api/auth.py` (DEV_USER_ID/DEV_USER_EMAIL) | SKIP_AUTH=true now authenticates against a real migrated Cosmos DB user instead of a synthetic stub |
| GitHub Actions CI/CD (both pipelines green) | deploy-swa.yml and deploy-api.yml auto-deploy on push to DEV; tests gate API deploy |
| KV role assignment (manual) | Function App managed identity confirmed reading secrets from kv-afdb-dev |
| `frontend/js/dashboard.js` fallback | Jobs with unrecoverable titles display "Position Closed" instead of blank cards |
| `staticwebapp.config.json` cleanup | Removed conflicting allowedRoles route guards; auth fully delegated to MSAL |

#### What You Can Test Now

| Thing to test | How |
|---|---|
| Legacy pipeline still works | `docker build -t afdb-tracker . && docker run --env-file .env afdb-tracker` |
| Live API health check | `curl https://func-afdb-dev.azurewebsites.net/api/health` |
| Live jobs endpoint | `curl "https://func-afdb-dev.azurewebsites.net/api/jobs" -H "x-skip-auth: true"` (dev mode) |
| Live dashboard | Open https://thankful-meadow-0f880790f.6.azurestaticapps.net |
| MSAL login flow | Click Sign In on the SWA landing page → Entra CIAM → redirect back to dashboard with real job data |
| All unit tests | `pip install -r requirements.txt && python -m pytest tests/ -v` |

#### Deferred

| Item | Reason |
|---|---|
| `kv-roles.bicep` Bicep idempotency fix (role ID format) | Role assigned manually and working; Bicep fix is cosmetic for re-deploys. Carry to Sprint 6. |
| `profile.js` → GET /api/profile pre-fill | Endpoint exists and tested; wiring the frontend call deferred. Save/update flow works. Carry to Sprint 6. |

#### Next Sprint Goal
Make the platform production-ready: deploy to `rg-afdb-prod`, automate the weekly pipeline in Container Apps Job, and add Application Insights alerting on pipeline failures.

---

## Sprint 5 — Production Readiness

**Goal**: Production environment deployed, weekly pipeline automated, monitoring live.
**Branch**: `dev`
**Status**: ✅ COMPLETE

### Sprint 5 Task Table

| # | Task | Owner | Priority | Status | Notes |
|---|------|-------|----------|--------|-------|
| S5-01 | Deploy Bicep to `rg-afdb-prod` (australiacentral) | devops-sec | P0 | ✅ Done | 7 resources live: Cosmos DB, KV, Storage, Function App (B1), SWA, App Service Plan, App Insights |
| S5-02 | Entra External ID: update redirect URIs to prod SWA URL + `env.js` prod routing | devops-sec | P0 | ✅ Done | Same dev tenant; env.js now detects prod hostname and routes to func-afdb-prod |
| S5-03 | GitHub Actions: prod deploy jobs on push to `main` | devops-sec | P0 | ✅ Done | deploy-swa.yml + deploy-api.yml both have prod jobs triggered on main |
| S5-04 | Container Apps Job: weekly cron | devops-sec | P0 | ⏭ Deferred | Bicep module ready; blocked on ACR Docker image (Sprint 6) |
| S5-05 | Build + push pipeline Docker image to ACR | backend-pipeline | P0 | ⏭ Deferred | Dockerfile.pipeline exists; deploy-pipeline.yml ready; blocked on ACR push (Sprint 6) |
| S5-06 | Application Insights wired to Function App | devops-sec | P1 | ✅ Done | appi-afdb-prod deployed; APPINSIGHTS_INSTRUMENTATIONKEY set on func-afdb-prod |
| S5-07 | Alert rule: email on Container Apps Job failure | devops-sec | P1 | ⏭ Deferred | alertrule.bicep exists; no job to monitor yet (Sprint 6) |
| S5-08 | `kv-roles.bicep` Bicep idempotency fix | devops-sec | P1 | ⏭ Deferred | Role works; carry to Sprint 6 |
| S5-09 | `profile.js` → GET /api/profile pre-fills all fields | web-frontend | P1 | ✅ Done | Wired in frontend/js/profile.js; all fields load from API |
| S5-10 | Migrate prod Cosmos DB | backend-pipeline | P1 | ✅ Done | 43 jobs + 43 evaluations migrated via migrate_duckdb_to_cosmos.py |
| S5-11 | Smoke test prod: health + jobs + register | delivery-lead | P0 | ✅ Done | /api/health 200, /api/register 201, /api/sources 200, prod SWA 200 |
| S5-12 | README SaaS setup section | delivery-lead | P2 | ✅ Done | 8-step bootstrap guide appended to README.md |
| S5-13 | Verify eval skip guard | backend-pipeline | P0 | ✅ Done | TestEvaluationSkipGuard (2 tests) added; all 25 tests green |
| S5-14 | Fix Cosmos DB public access (prod 500 bug) | devops-sec | P0 | ✅ Done | publicNetworkAccess was Disabled; B1 plan has no VNet — enabled via CLI + Bicep fixed |
| S5-15 | Set ENTRA_EXTERNAL_TENANT_ID + ENTRA_CLIENT_ID on func-afdb-prod | devops-sec | P0 | ✅ Done | JWT validation now functional on prod |

---

### Sprint 5 Review Summary — 2026-04-17

#### Completed

| Deliverable | What it does |
|---|---|
| `rg-afdb-prod` (7 resources) | Cosmos DB (standard tier), Key Vault, Storage, Function App B1, Static Web App, App Service Plan, App Insights all live in australiacentral |
| `func-afdb-prod` API | `/api/health` 200, `/api/register` 201, `/api/sources` 200 — all confirmed in prod |
| Prod Cosmos DB seeded | 43 real AfDB jobs + 43 evaluations migrated from DuckDB via `scripts/migrate_duckdb_to_cosmos.py` |
| `Dockerfile.pipeline` | Container image for weekly pipeline; Playwright + scrapers; ready for ACR push |
| `infrastructure/modules/alertrule.bicep` | New module: email alert on Container Apps Job failure via Log Analytics query |
| `infrastructure/modules/containerapp-job.bicep` | KV secret references for GEMINI_API_KEY + GMAIL_APP_PASSWORD via managed identity |
| `infrastructure/main.parameters.prod.json` | Prod deploy parameters (`scraperImageTag=''` for initial deploy before ACR) |
| `.github/workflows/deploy-pipeline.yml` | New: builds Docker image + pushes to ACR on push to `main` |
| `deploy-swa.yml` + `deploy-api.yml` | Prod deploy jobs added; triggered on push to `main` |
| `frontend/js/env.js` | Auto-detects prod hostname → routes `API_BASE` to `func-afdb-prod`; dev hostname → `func-afdb-dev` |
| `frontend/js/profile.js` | GET /api/profile now pre-fills all form fields on page load |
| `tests/test_pipeline_v2.py` | `TestEvaluationSkipGuard` (2 tests): verifies jobs with existing evaluations are never re-scored |
| README.md | Full 8-step SaaS bootstrap guide (Bicep deploy → Entra → GitHub secrets → seed → run) |
| Prod Cosmos DB fix | Root cause: `publicNetworkAccess: Disabled` blocked B1 plan (no VNet). Fixed in Bicep + applied via CLI |

#### What You Can Test Now

| Test | How |
|---|---|
| Prod API health | `curl https://func-afdb-prod.azurewebsites.net/api/health` |
| Prod registration | `curl -X POST https://func-afdb-prod.azurewebsites.net/api/register -H "Content-Type: application/json" -d '{"email":"you@example.com","name":"Test","profile_text":"Data engineer"}'` |
| Prod SWA | Open https://gray-ground-0b9535b0f.2.azurestaticapps.net |
| All unit tests | `python -m pytest tests/ -v` (25/25 green) |

#### Deferred to Sprint 6

| Item | Reason |
|---|---|
| Container Apps Job (weekly pipeline) | Needs Docker image pushed to ACR first — `deploy-pipeline.yml` ready, run after Entra prod redirect URI confirmed |
| Alert rule (pipeline failure) | No job to alert on yet; alertrule.bicep exists, deploys with scraperImageTag |
| `kv-roles.bicep` idempotency | Role assigned manually; Bicep cosmetic fix, carry forward |
| Merge DEV → main | Gate: Entra prod redirect URI confirmed + prod smoke test with real MSAL login passing |

#### Next Sprint Goal
Push Docker image to ACR, deploy Container Apps Job to prod, confirm weekly cron runs, merge DEV → main. **End of Phase I.**
