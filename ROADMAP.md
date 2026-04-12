# AfDB-Platform — Product Roadmap

> **Vision**: A multi-tenant SaaS platform where professionals register once and automatically receive personalized job alerts from multiple international organizations (AfDB, World Bank, UNDP, IMF, and more) via email and a unified web dashboard.

**Current state**: Single-user AfDB tracker (DuckDB + Playwright + Gemini + Gmail + Azure Blob)  
**Target state**: Multi-tenant SaaS (Cosmos DB + pluggable scrapers + Azure Functions API + Static Web Apps + Entra External ID)

---

## Phases

### Phase 0 — Foundation (Sprint 0) ✅ IN PROGRESS
**Goal**: Establish architecture, IaC skeleton, multi-source config, and cost model. Zero production changes.

- [ ] 5 subagent definitions in `.claude/agents/`
- [ ] ROADMAP.md + SPRINT_BACKLOG.md
- [ ] Living cost model (`docs/cost-model.md`)
- [ ] ADR-001: Database choice (Cosmos DB vs alternatives)
- [ ] ADR-002: Auth provider (Entra External ID)
- [ ] Bicep IaC skeleton (`infrastructure/`)
- [ ] Pluggable scraper skeleton (`scrapers/`, `scrapers/base.py`, `scrapers/config/sources.yaml`)
- [ ] `LEGACY_MODE` flag documented and gated in code
- [ ] DEV branch created, branch protection rules documented

---

### Phase 1 — Backend Core (Sprint 1–2)
**Goal**: Multi-tenant pipeline running locally; Cosmos DB integration complete; legacy pipeline unaffected.

- [ ] `src/cosmos_db.py` — Cosmos DB client (async, managed identity)
- [ ] `scrapers/afdb/scraper.py` — wraps existing Playwright scraper into BaseScraper
- [ ] `scrapers/worldbank/scraper.py` — World Bank Jobs scraper (Playwright or API)
- [ ] Dual-mode pipeline (`LEGACY_MODE=true` → DuckDB, `false` → Cosmos DB)
- [ ] Per-user evaluation: score each job against each user's profile
- [ ] Gemini vector embeddings stored in Cosmos DB
- [ ] `src/evaluator_v2.py` — vector shortlist (top-50) + Gemini re-rank
- [ ] `src/notifier_v2.py` — per-user email with multi-source job list
- [ ] End-to-end local test: 2 users, 2 sources, correct emails sent

---

### Phase 2 — API Layer (Sprint 3)
**Goal**: REST API deployable to Azure Functions; user CRUD operations complete.

- [ ] `api/main.py` — FastAPI app (Azure Functions compatible)
- [ ] `POST /api/register` — create user, send verification email
- [ ] `GET /api/verify` — verify email token
- [ ] `GET /api/jobs` — paginated, filtered job list for authenticated user
- [ ] `PUT /api/profile` — update career objectives + source preferences
- [ ] `GET /api/sources` — list available job sources
- [ ] Entra External ID OIDC integration
- [ ] Key Vault references for all secrets
- [ ] API deployed to Azure Functions dev environment

---

### Phase 3 — Frontend (Sprint 4)
**Goal**: Working web UI on Azure Static Web Apps dev environment.

- [ ] `frontend/` folder with `staticwebapp.config.json`
- [ ] Landing page + MSAL login flow
- [ ] Registration wizard (email → verify → profile setup)
- [ ] Unified job dashboard (multi-source, filterable, sortable)
- [ ] Profile editor (career objectives, source toggles, score threshold)
- [ ] Score badges + source badges (color-coded)
- [ ] Deployed to Static Web Apps dev slot

---

### Phase 4 — Infrastructure & CI/CD (Sprint 5)
**Goal**: Full Bicep deployment to dev/qa environments; GitHub Actions CI/CD active.

- [ ] All Bicep modules complete (Cosmos DB, Container Apps Job, Functions, Static Web Apps, Key Vault)
- [ ] `infrastructure/scripts/deploy.sh` — one-command deploy per environment
- [ ] GitHub Actions: `dev.yml`, `qa.yml`, `main.yml`
- [ ] Legacy Docker pipeline runs as a CI sanity check in every workflow
- [ ] Budget alerts configured in Azure Cost Management
- [ ] Penetration test checklist completed

---

### Phase 5 — Beta Launch (Sprint 6)
**Goal**: Real users can register, receive emails, and use the dashboard.

- [ ] Entra External ID tenant configured in prod
- [ ] prod Bicep deployment
- [ ] 5 beta users onboarded
- [ ] ≥2 job sources active (AfDB + World Bank minimum)
- [ ] Weekly pipeline confirmed running in Container Apps Job
- [ ] Monitoring: Application Insights alerts on pipeline failures
- [ ] README updated for SaaS setup

---

### Phase 6 — Scale & Sources (Sprint 7+)
**Goal**: Add more sources, optimize costs, improve UX.

- [ ] UNDP scraper
- [ ] IMF scraper
- [ ] ADB (Asian Development Bank) scraper
- [ ] Cosmos DB vector index optimization
- [ ] Source health monitoring (alert if a scraper returns 0 jobs)
- [ ] User-managed source subscriptions
- [ ] Admin dashboard (job source status, user count, pipeline logs)

---

## Architecture Summary

```
[Weekly Container Apps Job]
  scrapers/ (AfDB, World Bank, UNDP, IMF, ...)
        ↓
[Azure Cosmos DB — NoSQL + vector index]
  jobs | users | evaluations
        ↓
[Azure Functions — FastAPI API]
  /register | /verify | /jobs | /profile | /sources
        ↓
[Azure Static Web Apps — Frontend]
  dashboard | profile editor | signup flow
        ↓
[Microsoft Entra External ID — Auth]
```

## Non-negotiables

1. Legacy DuckDB pipeline (`LEGACY_MODE=true`) must run forever
2. Cosmos DB free tier: 1,000 RU/s + 25 GB — never exceed without FinOps approval
3. All secrets in Key Vault — no plaintext in code or containers
4. DEV → QA → MAIN branch strategy — no direct commits to main
5. Ethical scraping: 1 req/2s rate limit, respect robots.txt, weekly cadence only
