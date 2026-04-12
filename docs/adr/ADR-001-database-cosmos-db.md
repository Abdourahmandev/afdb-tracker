# ADR-001: Database — Azure Cosmos DB for NoSQL

**Date**: 2026-04-12  
**Status**: Accepted  
**Deciders**: arch-fin  

---

## Context

The legacy pipeline uses DuckDB (local file-based OLAP database). For the multi-tenant SaaS, we need:
- Multi-user data isolation (per-user evaluations, per-user preferences)
- Vector similarity search for job-to-profile matching (avoid full LLM re-ranking every job for every user)
- Serverless / consumption pricing (no always-on database server)
- Free tier that covers development and early production

Candidates evaluated:
1. **Azure Cosmos DB for NoSQL** (with vector search preview)
2. **Azure SQL Database** (serverless tier)
3. **Azure Table Storage** (simple key-value)
4. **PostgreSQL on Azure** (Flexible Server or serverless)
5. **DuckDB** (current, scale-out not viable)

---

## Decision

**Use Azure Cosmos DB for NoSQL with vector search.**

---

## Rationale

| Criterion | Cosmos DB NoSQL | Azure SQL Serverless | Table Storage | PostgreSQL |
|-----------|----------------|---------------------|---------------|------------|
| Free tier | ✅ 1,000 RU/s + 25 GB | ❌ None (min ~$5/month) | ✅ (but no vector) | ❌ None |
| Vector search | ✅ Built-in (preview) | ❌ (separate Azure AI Search needed) | ❌ | ✅ (pgvector, separate install) |
| Serverless / consumption | ✅ Consumption mode | ✅ | ✅ | ❌ Min 1 vCore always-on |
| Schema flexibility | ✅ Document model | ❌ Schema migrations | ✅ | ❌ Schema migrations |
| Azure Functions integration | ✅ Native binding | ✅ | ✅ | ✅ (manual) |
| Partition strategy | ✅ `source_id` for jobs, `user_id` for users/evaluations | N/A | Limited | N/A |

**Key factors**:
1. **Free tier covers us to ~500 users** — see cost model. No other option offers a free tier that includes vector search.
2. **Vector search eliminates O(users × jobs) LLM calls** — embed jobs once, shortlist top-50 per user via vector similarity, only re-rank the shortlist with Gemini. At 50 users × 200 jobs, this reduces Gemini calls by 75%.
3. **Document model fits scraper output** — jobs from different sources have varying schemas. NoSQL handles this without migrations.
4. **Partition key design scales well**: `source_id` for jobs (cross-user reads), `user_id` for evaluations (per-user reads).

---

## Consequences

**Good:**
- $0/month cost up to ~500 users
- Vector search built-in — no separate Azure AI Search ($~73/month minimum)
- Idempotent upserts via `jobs.id = f"{source_id}-{job_id}"`
- Schema evolution without migrations

**Bad / Watch:**
- Cosmos DB SDK is async-first (minor complexity)
- Vector search is in preview — may not be GA by Sprint 1 (fallback: keyword search with Cosmos DB full-text)
- Free tier is one per subscription — must share account across dev/qa/prod via separate databases
- RU/s capacity planning required: bursty scraper writes vs. steady user reads

**Fallback if vector search is not available:**
1. Use Cosmos DB full-text search for shortlisting
2. Or store embeddings in Cosmos DB and compute similarity in Python (cosine similarity on top-N with text filter first)

---

## Cost Impact

~$0/month up to 25 GB storage and 1,000 RU/s sustained. See `docs/cost-model.md` for full breakdown.

---

## Migration from DuckDB

The legacy DuckDB pipeline remains active under `LEGACY_MODE=true`. Migration is additive:
- New `src/cosmos_db.py` module created alongside existing `src/db.py`
- Pipeline checks `LEGACY_MODE` env var and routes to correct storage
- DuckDB file (`data/jobs.duckdb`) is never touched by the new code path
