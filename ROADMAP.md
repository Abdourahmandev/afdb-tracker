# AfDB-Platform — Product Roadmap

> **Vision**: A multi-tenant SaaS platform where professionals register once and automatically receive personalized job alerts from multiple international organizations (AfDB, World Bank, UNDP, IMF, and more) via email and a unified web dashboard.

**Current state**: Single-user AfDB tracker (DuckDB + Playwright + Gemini + Gmail + Azure Blob)  
**Target state**: Multi-tenant SaaS (Cosmos DB + pluggable scrapers + Azure Functions API + Static Web Apps + Entra External ID)

---

## Phase I — Launch (Sprints 0–6)

> **Goal**: Get the first real user on the platform. AfDB as the sole job source. Everything functional, nothing polished.
> **Done when**: A real user registers, receives a personalized job alert email, and browses their dashboard.

---

### Phase I · Sprint 0 — Foundation ✅ COMPLETE
**Goal**: Establish architecture, IaC skeleton, multi-source config, and cost model. Zero production changes.

- [x] 5 subagent definitions in `.claude/agents/`
- [x] ROADMAP.md + SPRINT_BACKLOG.md
- [x] Living cost model (`docs/cost-model.md`)
- [x] ADR-001: Database choice (Cosmos DB vs alternatives)
- [x] ADR-002: Auth provider (Entra External ID)
- [x] Bicep IaC skeleton (`infrastructure/`)
- [x] Pluggable scraper skeleton (`scrapers/`, `scrapers/base.py`, `scrapers/config/sources.yaml`)
- [x] `LEGACY_MODE` flag documented and gated in code

---

### Phase I · Sprint 1–2 — Backend Core ✅ COMPLETE
**Goal**: Multi-tenant pipeline running locally; Cosmos DB integration complete; legacy pipeline unaffected.

- [x] `src/cosmos_db.py` — Cosmos DB client
- [x] `scrapers/afdb/scraper.py` — AfDB scraper wrapped in BaseScraper
- [x] Dual-mode pipeline (`LEGACY_MODE=true` → DuckDB, `false` → Cosmos DB)
- [x] `src/evaluator_v2.py` — per-user Gemini scoring
- [x] `src/notifier_v2.py` — per-user digest email
- [x] `src/pipeline_v2.py` — multi-tenant orchestrator
- [x] End-to-end local test: 2 users, correct evaluations + emails

---

### Phase I · Sprint 3 — API Layer ✅ COMPLETE
**Goal**: REST API deployable to Azure Functions; user CRUD operations complete.

- [x] `api/main.py` — FastAPI app (Azure Functions v2 ASGI)
- [x] `POST /api/register`, `GET /api/verify`, `GET /api/jobs`, `PUT /api/profile`, `GET /api/sources`
- [x] `api/auth.py` — Entra External ID JWT validation + `SKIP_AUTH` dev bypass
- [x] `scripts/seed_cosmos.py` — dev seed script
- [x] 16 integration tests

---

### Phase I · Sprint 4 — Frontend ✅ COMPLETE
**Goal**: Working web UI on Azure Static Web Apps dev environment.

- [x] Landing page + MSAL login flow
- [x] Registration wizard (3 steps: email → profile → preferences)
- [x] Job dashboard (multi-source, filterable, paginated, score badges)
- [x] Profile editor (career text, source toggles, score threshold)
- [x] GitHub Actions CI/CD: `deploy-swa.yml` + `deploy-api.yml`

---

### Phase I · Sprint 5 — Infrastructure & CI/CD 🔄 IN PROGRESS
**Goal**: All Azure resources live in dev; API confirmed reachable; SWA deployed.

- [x] All 8 Azure resources provisioned (`rg-afdb-dev`, australiacentral)
- [x] API live: `func-afdb-dev` → `GET /api/health` returns 200
- [x] Cosmos DB seeded; `GET /api/jobs` returns scored results
- [ ] `GET /api/profile` endpoint added
- [ ] `GET /api/sources` 500 error fixed (sources.yaml missing from zip)
- [ ] SWA deployed (`AZURE_STATIC_WEB_APPS_API_TOKEN_DEV` GitHub secret set)
- [ ] KV role assignment fixed (`kv-roles.bicep` role ID)
- [ ] Entra External ID tenant configured (follow `docs/entra-setup.md`)
- [ ] GitHub Actions secrets configured; CI/CD pipelines green

---

### Phase I · Sprint 6 — Beta Launch
**Goal**: First real user registers, receives a job alert, and uses the dashboard. **End of Phase I.**

- [ ] Prod Bicep deployment (`rg-afdb-prod`)
- [ ] Entra External ID configured in prod
- [ ] First real user onboarded end-to-end
- [ ] Weekly pipeline confirmed running in Container Apps Job (prod)
- [ ] Application Insights alerts on pipeline failures
- [ ] README updated for SaaS setup

> ⚠️ **Non-negotiable before prod deploy**: The pipeline must skip re-evaluation of jobs that already have a score in the `evaluations` container. Check `cosmos_db.get_evaluated_job_ids_for_user()` is called before every Gemini call — never re-spend tokens on a job a user has already seen. Verify this with a unit test before Sprint 6 ships.

---

## Phase II — Premium UX (Sprint 7)

> **Goal**: Completely redesign the frontend into a sophisticated, modern product that can be shown to investors and real users. The MVP UI from Phase I is replaced entirely.
> **Starts after**: First real user launched (Sprint 6 complete).

### Phase II · Sprint 7 — UI Redesign
**Goal**: Replace the functional-but-plain Phase I frontend with a polished, professional design system.

- [ ] Design system: typography scale, color palette, spacing tokens, component library
- [ ] New landing page — hero section, feature highlights, social proof, CTA
- [ ] Animated job cards with source branding, match score ring indicator
- [ ] Dashboard redesign: split-pane layout, advanced filters sidebar, saved searches
- [ ] Profile editor redesign: rich text career profile, drag-and-drop source ordering
- [ ] Responsive mobile-first layout (dashboard usable on phone)
- [ ] Dark mode support
- [ ] Micro-animations and loading skeletons
- [ ] Onboarding flow redesign: step progress indicator, inline validation, tooltips
- [ ] Accessibility audit: WCAG 2.1 AA compliance

---

## Phase III — Multi-Source Expansion (Sprint 8+)

> **Goal**: Add more job sources and scale the platform. World Bank is the first new source.
> **Starts after**: UI redesign complete (Sprint 7).

### Phase III · Sprint 8 — World Bank + Source Framework
- [ ] `scrapers/worldbank/scraper.py` — real World Bank Jobs scraper
- [ ] Source health monitoring (alert if scraper returns 0 jobs)
- [ ] Admin dashboard: source status, user count, pipeline logs
- [ ] User-managed source subscriptions UI

### Phase III · Sprint 9+ — Additional Sources
- [ ] UNDP scraper
- [ ] IMF scraper
- [ ] ADB (Asian Development Bank) scraper
- [ ] Cosmos DB vector index optimization (DiskANN, dedicated throughput)
- [ ] Multi-source deduplication (same job posted on multiple boards)

---

## Phase IV — Profile-Based Evaluation Engine (Sprint 10+)

> **Goal**: Replace per-user Gemini evaluation with a scalable profile-tagging system. At low user counts, re-running Gemini per user is manageable. At scale (100+ users), re-analysing every job for every user becomes prohibitively expensive. This phase eliminates that cost entirely.
>
> **Core idea**: Jobs are analysed once. Users are matched to jobs via predefined professional profiles (tags), not by running Gemini against each user's raw profile text.

### How it works

```
[New job scraped]
        ↓
[Gemini analyses job once → assigns profile tags]
  e.g. ["data-engineer", "python", "azure", "senior"]
        ↓
[Cosmos DB jobs container — tags stored on job document]
        ↓
[New user registers → selects profile tags they match]
  e.g. user selects: "data-engineer", "azure"
        ↓
[Matching: query jobs WHERE tags INTERSECT user.profiles]
  No Gemini call needed for existing jobs.
  Score = tag overlap ratio (fast, deterministic, free).
```

### Predefined profile taxonomy (initial set)
| Domain | Profiles |
|---|---|
| Data & Analytics | `data-engineer`, `data-analyst`, `data-scientist`, `bi-developer`, `data-governance` |
| Finance | `accountant`, `financial-analyst`, `budget-officer`, `auditor`, `treasury` |
| IT & Engineering | `software-engineer`, `devops`, `cybersecurity`, `it-support`, `project-manager-tech` |
| Development | `economist`, `project-manager`, `procurement`, `communications`, `hr` |
| Leadership | `director`, `vp`, `chief-officer`, `team-lead` |

### Sprint 10 — Profile Taxonomy & Job Tagging
- [ ] Define canonical profile taxonomy (stored in `scrapers/config/profiles.yaml`)
- [ ] `src/tagger.py` — Gemini tags each new job once on ingest; result stored in `jobs.profiles[]`
- [ ] Migration script: retag all existing jobs in Cosmos DB with profiles
- [ ] Skip tagging if `job.profiles` already populated (idempotent ingest)
- [ ] Unit tests: tagging output matches expected profiles for sample job descriptions

### Sprint 11 — User Profile Tags & Matching Engine
- [ ] Registration wizard updated: user selects matching profiles from taxonomy (multi-select)
- [ ] `PUT /api/profile` updated: accepts `profiles[]` array alongside existing `profile_text`
- [ ] `src/matcher.py` — tag-intersection scoring: replaces Gemini per-user call for existing jobs
- [ ] Pipeline updated: new jobs → tag → match all users by profile → notify; Gemini only called once per job
- [ ] Fallback: users with no tags selected still get Gemini scoring (graceful degradation)
- [ ] Cost model updated: document Gemini call reduction at 10 / 100 / 1000 users

### Sprint 12 — Profile UX & Refinement
- [ ] Dashboard filter: filter jobs by profile tag
- [ ] Profile page: show matched profiles, allow editing tag selection
- [ ] Tag confidence score shown on job cards (e.g. "3/5 tags matched")
- [ ] Admin view: most common profiles, tag distribution across jobs

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
