// Azure Functions — API layer (Consumption plan, Python 3.12)
// Hosts the FastAPI-based REST API for the AfDB-Platform

param prefix string
param environment string
param location string
param tags object
param keyVaultName string
param cosmosDbEndpoint string
param cosmosDbDatabaseName string

var storageAccountName = 'stfunc${prefix}${environment}'   // Must be globally unique, 24 chars max
var hostingPlanName = 'asp-${prefix}-${environment}'
var functionsAppName = 'func-${prefix}-${environment}'
var appInsightsName = 'appi-${prefix}-${environment}'

// ─── Storage Account for Functions runtime ───────────────────────────────────

resource funcStorage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    supportsHttpsTrafficOnly: true
  }
}

// ─── Application Insights ────────────────────────────────────────────────────

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    RetentionInDays: 30
  }
}

// ─── Hosting Plan ────────────────────────────────────────────────────────────
// Dev uses B1 Basic (~$13/month) — Y1/Dynamic requires Dynamic VMs quota (0 by default
// in new subscriptions). Request a quota increase at portal.azure.com → Subscriptions →
// Usage + Quotas, then change to: sku { name: 'Y1', tier: 'Dynamic' }.
// Non-dev uses Y1 Consumption (pay-per-execution, scale-to-zero).

// F1 (Free/Shared) requires no VM quota — suitable for dev/testing.
// Switch to Y1 (Consumption) or B1 (Basic) once quota is granted at:
// portal.azure.com → Subscriptions → Usage + Quotas → request increase.
// B1 Basic for all environments — Y1 Consumption requires Dynamic VMs quota which
// is zero in this subscription. Request increase at portal.azure.com → Subscriptions →
// Usage + Quotas if scale-to-zero billing is needed in future.
var planSku = { name: 'B1', tier: 'Basic' }

resource hostingPlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: hostingPlanName
  location: location
  tags: tags
  sku: planSku
  properties: {
    reserved: true   // Linux
  }
}

// ─── Function App ────────────────────────────────────────────────────────────

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name: functionsAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: hostingPlan.id
    reserved: true
    siteConfig: {
      linuxFxVersion: 'Python|3.12'
      pythonVersion: '3.12'
      functionAppScaleLimit: 10   // Limit scale to avoid surprise costs
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${funcStorage.name};AccountKey=${funcStorage.listKeys().keys[0].value}'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsights.properties.InstrumentationKey
        }
        {
          name: 'COSMOS_ENDPOINT'
          value: cosmosDbEndpoint
        }
        {
          name: 'COSMOS_DATABASE'
          value: cosmosDbDatabaseName
        }
        {
          name: 'ENVIRONMENT'
          value: environment
        }
        {
          name: 'KEY_VAULT_NAME'
          value: keyVaultName
        }
        {
          name: 'API_BASE_URL'
          value: 'https://func-${prefix}-${environment}.azurewebsites.net'
        }
      ]
      cors: {
        // Allow both the generic SWA name and the actual Azure-assigned hostname.
        // The actual hostname (e.g. gray-ground-*.azurestaticapps.net) is assigned
        // by Azure at SWA creation time and cannot be predicted in Bicep, so we
        // use a wildcard pattern via the FastAPI CORSMiddleware (allow_origin_regex)
        // and also allow all *.azurestaticapps.net here at the platform level.
        allowedOrigins: [
          'https://swa-afdb-${environment}.azurestaticapps.net'
          'https://*.azurestaticapps.net'
        ]
        supportCredentials: true
      }
    }
    httpsOnly: true
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

output functionAppId string = functionApp.id
output defaultHostname string = functionApp.properties.defaultHostName
output principalId string = functionApp.identity.principalId
output functionAppName string = functionApp.name
