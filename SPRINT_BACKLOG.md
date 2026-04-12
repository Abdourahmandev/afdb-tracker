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

## Sprint 3 — Frontend (UPCOMING)

| # | Task | Owner | Priority |
|---|------|-------|----------|
| S3-01 | `frontend/` folder structure + `staticwebapp.config.json` | web-frontend | HIGH |
| S3-02 | Landing page (`index.html`) with login button | web-frontend | HIGH |
| S3-03 | MSAL.js auth module (`frontend/js/auth.js`) | web-frontend | HIGH |
| S3-04 | Registration wizard — email → verify → profile setup | web-frontend | HIGH |
| S3-05 | Job dashboard (`dashboard.html`) — multi-source, filterable, sortable | web-frontend | HIGH |
| S3-06 | Profile editor (`profile.html`) — career text, source toggles, score slider | web-frontend | HIGH |
| S3-07 | API client module (`frontend/js/api.js`) — fetch wrappers with auth headers | web-frontend | HIGH |
| S3-08 | Source + score badges (color-coded, match legacy dashboard style) | web-frontend | MEDIUM |
| S3-09 | Deploy to Azure Static Web Apps dev slot | devops-sec | MEDIUM |
| S3-10 | Entra External ID tenant setup (manual — Azure Portal) | devops-sec | HIGH |
