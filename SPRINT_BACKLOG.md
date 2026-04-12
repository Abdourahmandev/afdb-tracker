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

## Sprint 2 — API Layer (UPCOMING)

| # | Task | Owner | Priority |
|---|------|-------|----------|
| S2-01 | `api/main.py` — FastAPI app (Azure Functions v2 Python model) | backend-pipeline | HIGH |
| S2-02 | `POST /api/register` — create user, send verification email | backend-pipeline | HIGH |
| S2-03 | `GET /api/verify` — verify email token, activate user | backend-pipeline | HIGH |
| S2-04 | `GET /api/jobs` — paginated, filtered job list for authenticated user | backend-pipeline | HIGH |
| S2-05 | `PUT /api/profile` — update profile text + source preferences | backend-pipeline | HIGH |
| S2-06 | `GET /api/sources` — list available job sources from sources.yaml | backend-pipeline | LOW |
| S2-07 | Entra External ID OIDC token validation middleware | backend-pipeline | HIGH |
| S2-08 | Deploy Functions to dev environment via Bicep | devops-sec | HIGH |
| S2-09 | Cosmos DB dev seed script | backend-pipeline | MEDIUM |
| S2-10 | API integration tests (mocked, no cloud) | backend-pipeline | MEDIUM |
