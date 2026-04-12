# AfDB-Platform — Living Cost Model

> **Owner**: arch-fin  
> **Last updated**: 2026-04-12  
> **Status**: Sprint 0 — pre-deployment estimates

This document is the authoritative cost reference. Update it whenever infrastructure changes. FinOps approval is required for any change that increases monthly cost by >$5.

---

## Azure Services & Pricing Tiers

### 1. Azure Cosmos DB for NoSQL — FREE TIER

| Resource | Free Tier Limit | Our Usage (50 users) | Usage (500 users) |
|----------|----------------|----------------------|-------------------|
| Provisioned throughput | 1,000 RU/s shared | ~200 RU/s avg | ~600 RU/s avg |
| Storage | 25 GB | ~2 GB | ~15 GB |
| Vector search | Included (preview) | Yes | Yes |
| **Monthly cost** | **$0** | **$0** | **$0** |

**Free tier claim**: One free-tier account per Azure subscription. We claim it on `cosmos-afdb-dev` and reuse the same account across environments via separate databases.

**RU/s estimate per weekly run:**
- 200 job upserts × 10 RU = 2,000 RU
- 50 users × 200 job reads (vector query) = 10 RU each = 100,000 RU
- 50 users × 50 evaluations upsert × 10 RU = 25,000 RU
- **Total per run**: ~127,000 RU over ~5 minutes = 427 RU/s peak
- **Within free tier**: 1,000 RU/s ✅

**25 GB storage estimate:**
- 1 job doc: ~5 KB (including embedding ~4 KB at 1536 dims × float32)
- 1,000 jobs/year × 5 KB = 5 MB for jobs
- 500 users × 2 KB = 1 MB for users
- 500 users × 1,000 evaluations × 1 KB = 500 MB for evaluations (3 years)
- **Total (3 years)**: ~506 MB — far below 25 GB ✅

---

### 2. Azure Container Apps Jobs (Consumption) — NEAR-FREE

| Resource | Free Allotment | Our Usage | Cost |
|----------|---------------|-----------|------|
| vCPU-seconds | 180,000/month | ~1,560/month | $0 |
| Memory GiB-seconds | 360,000/month | ~3,120/month | $0 |

**Calculation:**
- 1 run/week × 4.3 weeks/month = 4.3 runs/month
- Each run: ~6 minutes = 360 seconds
- 1 vCPU × 360s = 360 vCPU-seconds/run × 4.3 = **1,548 vCPU-seconds/month**
- Free allotment: 180,000 — **we use 0.9%** ✅
- **Monthly cost**: $0

---

### 3. Azure Static Web Apps — FREE TIER

| Feature | Free Tier |
|---------|-----------|
| Bandwidth | 100 GB/month |
| Custom domains | 2 |
| Preview environments | 3 |
| Authentication (Entra) | Included |
| **Monthly cost** | **$0** |

---

### 4. Azure Functions (Consumption Plan) — NEAR-FREE

| Resource | Free Allotment | Our Usage (50 users) | Cost |
|----------|---------------|----------------------|------|
| Executions | 1 million/month | ~5,000/month | $0 |
| GB-seconds | 400,000/month | ~10,000/month | $0 |

**Calculation:** 50 users × `/api/jobs` weekly refresh = 200 calls/day × 30 = 6,000/month. Each call ~200ms × 256 MB = 51 GB-seconds/month. **Within free tier** ✅

---

### 5. Microsoft Entra External ID — FREE TIER

| Resource | Free Tier | Cost |
|----------|-----------|------|
| Monthly Active Users | 50,000 | $0 |
| MFA authentications | 50,000/month | $0 |
| **Monthly cost** | | **$0** |

---

### 6. Azure Key Vault — NEAR-FREE

| Resource | Price | Our Usage | Monthly Cost |
|----------|-------|-----------|-------------|
| Secret operations | $0.03/10,000 | ~1,000/month | $0.003 |
| Certificate operations | N/A | 0 | $0 |
| **Monthly cost** | | | **~$0.01** |

---

### 7. Azure Blob Storage (Legacy report.html) — EXISTING

| Resource | Price | Usage | Monthly Cost |
|----------|-------|-------|-------------|
| LRS storage | $0.018/GB | 1 MB | $0.000018 |
| Write operations | $0.05/10,000 | 4/month | $0.00002 |
| **Monthly cost** | | | **~$0.01** |

---

### 8. Azure Container Registry (Legacy — existing)

| SKU | Monthly Cost |
|-----|-------------|
| Basic | $0.167/day = **$5/month** |

> **Note**: ACR Basic is the only non-free resource. Already paid for legacy pipeline. No change in Sprint 0. FinOps review in Sprint 4: consider migrating to GitHub Container Registry (free) to eliminate this cost.

---

## Monthly Cost Summary

| Scenario | Cost/Month | Notes |
|----------|-----------|-------|
| **Sprint 0 (no new resources)** | **$5.01** | Just existing ACR Basic |
| **Sprint 1–3 (dev environment)** | **~$5.02** | +Key Vault micro-costs |
| **50 users (production)** | **~$5.03** | All within free tiers |
| **500 users (growth)** | **~$5.10** | Still within free tiers |
| **1,000+ users or >25 GB** | **TBD** | Cosmos DB Standard S1: ~$24/month |

**The platform is effectively free to run up to ~500 users** on the current architecture, minus the $5/month ACR Basic charge (which can be eliminated by switching to GitHub Container Registry).

---

## Cost Scaling Thresholds

| Threshold | Trigger | Action |
|-----------|---------|--------|
| >1,000 RU/s sustained | Cosmos DB free tier limit | Scale to Standard S1 (~$24/month) |
| >25 GB storage | Cosmos DB free tier limit | Evaluate compression or archive policy |
| >50,000 MAU | Entra free tier limit | Entra External ID P1: $0.01625/MAU |
| >1M Functions calls/month | Functions free tier | ~$0.20 per additional million |

---

## Gemini API Cost (LLM Scoring)

> Using Google Gemini 2.0 Flash (free tier: 1M tokens/day, 15 req/min)

| Scenario | Tokens/week | Cost |
|----------|-------------|------|
| 50 users × 50 jobs × 500 tokens | 1,250,000 | Within free daily limit (split over 2 days) |
| 500 users × 50 jobs × 500 tokens | 12,500,000 | **Exceeds free tier** → $0.10/1M input tokens = ~$1.25/week |

**FinOps flag**: At 500+ users, Gemini costs ~$5/month. Mitigation: vector shortlist reduces re-evaluation; caching prevents duplicate evaluations.

---

## Budget Alert Recommendation

Configure in Azure Cost Management:
- Alert 1: Monthly forecast > $10 → email abdourahman03@gmail.com
- Alert 2: Monthly actual > $15 → email + pause non-critical resources

---

*Update this file in every sprint that adds or changes Azure resources.*
