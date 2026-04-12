// Azure Key Vault — Secrets management
// All application secrets stored here; accessed via managed identities

param prefix string
param environment string
param location string
param tags object

@secure()
param geminiApiKey string = ''

@secure()
param gmailAppPassword string = ''

param entraExternalTenantId string = ''
param entraClientId string = ''

var kvName = 'kv-${prefix}-${environment}'

// ─── Key Vault ───────────────────────────────────────────────────────────────

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: kvName
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true      // Use RBAC instead of legacy access policies
    enableSoftDelete: true
    softDeleteRetentionInDays: 7       // Minimum — dev environment
    enablePurgeProtection: environment == 'prod'  // Only in prod
    publicNetworkAccess: 'Enabled'     // Restrict further in prod via network rules
    networkAcls: {
      defaultAction: 'Allow'   // TODO Sprint 5: restrict to Functions + Container Apps outbound IPs
      bypass: 'AzureServices'
    }
  }
}

// ─── Secrets ─────────────────────────────────────────────────────────────────
// Only create secrets if values are provided (avoids empty secret errors)

resource geminiSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(geminiApiKey)) {
  parent: keyVault
  name: 'gemini-api-key'
  properties: {
    value: geminiApiKey
    attributes: {
      enabled: true
    }
  }
}

resource gmailSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(gmailAppPassword)) {
  parent: keyVault
  name: 'gmail-app-password'
  properties: {
    value: gmailAppPassword
    attributes: {
      enabled: true
    }
  }
}

// Non-secret config stored as Key Vault secrets for versioning
resource entraSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(entraExternalTenantId)) {
  parent: keyVault
  name: 'entra-external-tenant-id'
  properties: {
    value: entraExternalTenantId
  }
}

resource entraClientSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(entraClientId)) {
  parent: keyVault
  name: 'entra-client-id'
  properties: {
    value: entraClientId
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

output keyVaultId string = keyVault.id
output keyVaultName string = keyVault.name
output keyVaultUri string = keyVault.properties.vaultUri
