# ADR-002: Authentication — Microsoft Entra External ID

**Date**: 2026-04-12  
**Status**: Accepted  
**Deciders**: arch-fin  

---

## Context

The multi-tenant SaaS needs user registration, email verification, and secure login. Requirements:
- Self-service registration (email + password minimum)
- Email verification before first scan
- Token-based auth for Azure Functions API (JWT)
- Azure-native integration (managed identity, Azure Functions binding)
- Free tier sufficient for early user base (<50,000 MAU)

Candidates:
1. **Microsoft Entra External ID** (formerly Azure AD B2C)
2. **Firebase Auth** (Google)
3. **Auth0**
4. **Custom JWT** (DIY with Azure Functions)
5. **AWS Cognito**

---

## Decision

**Use Microsoft Entra External ID (workforce tenant, external user flows).**

---

## Rationale

| Criterion | Entra External ID | Firebase Auth | Auth0 | Custom JWT |
|-----------|-------------------|--------------|-------|------------|
| Free tier | ✅ 50,000 MAU | ✅ 10,000 MAU | ✅ 7,500 MAU | ✅ (no external cost) |
| Azure-native | ✅ | ❌ | ❌ | ✅ |
| MSAL.js support | ✅ First-class | ❌ | Partial | N/A |
| Email verification built-in | ✅ | ✅ | ✅ | ❌ Must build |
| Static Web Apps integration | ✅ Native | ❌ Manual | ❌ Manual | ❌ Manual |
| MFA support | ✅ | ✅ | ✅ | ❌ Must build |
| Social login (Google, etc.) | ✅ | ✅ | ✅ | ❌ Must build |
| Compliance (GDPR, etc.) | ✅ Microsoft compliance | ✅ | ✅ | ❌ Must build |

**Key factors**:
1. **Azure-native**: Static Web Apps has built-in Entra External ID authentication — zero custom auth middleware needed.
2. **50,000 MAU free** — sufficient for years 1–2.
3. **MSAL.js**: First-class JavaScript library, well-maintained, handles token refresh automatically.
4. **Email verification**: Built-in user flows, no custom code needed.
5. **Ecosystem lock-in is acceptable**: We are already Azure-native (Cosmos DB, Functions, Static Web Apps). Entra centralizes identity in the same ecosystem.

---

## Consequences

**Good:**
- $0/month up to 50,000 MAU
- No custom auth code (reduces attack surface)
- Managed Identity chain: user → Entra token → Functions → Cosmos DB (no connection strings)
- Built-in MFA, social login, password reset

**Bad / Watch:**
- Entra External ID requires a separate tenant (not the same as a corporate Microsoft 365 tenant)
- Configuration is in Azure Portal — not fully Bicep-able (tenant setup is manual once)
- Learning curve for MSAL.js token scopes and claims

**Setup steps (one-time, manual):**
1. Create Entra External ID tenant in Azure Portal
2. Register app (single-page application) → get `clientId` and `tenantId`
3. Configure user flows: sign-up/sign-in with email verification
4. Set redirect URIs: `https://swa-afdb-dev.azurestaticapps.net/login`
5. Store `clientId` and `tenantId` in Key Vault (non-secret, but versioned)

---

## Cost Impact

$0/month up to 50,000 MAU. See `docs/cost-model.md`.

---

## Integration Notes

```javascript
// MSAL configuration (frontend/js/auth.js)
const msalConfig = {
  auth: {
    clientId: process.env.ENTRA_CLIENT_ID,
    authority: `https://{tenant}.ciamlogin.com/{tenant}.onmicrosoft.com`,
    redirectUri: window.location.origin + '/login'
  }
};
```

```python
# Azure Functions token validation (api/auth_middleware.py)
# Use azure-identity + msal to validate Bearer tokens from Entra
from azure.identity import DefaultAzureCredential
# Token validation via JWKS endpoint from Entra tenant
```
