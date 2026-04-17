// Azure Container Apps Job — Weekly Scraper
// Consumption plan (pay-per-use), system-assigned managed identity
// Runs all enabled scrapers on a weekly CRON schedule.
// Secrets (GEMINI_API_KEY, GMAIL_APP_PASSWORD) are read from Key Vault via managed identity.

param prefix string
param environment string
param location string
param tags object
param scraperImageTag string
param cosmosDbEndpoint string
param cosmosDbDatabaseName string
param storageAccountName string
param keyVaultName string

var appEnvName = 'cae-${prefix}-${environment}'
var jobName = 'ca-job-${prefix}-${environment}'
var keyVaultUrl = 'https://${keyVaultName}${az.environment().suffixes.keyvaultDns}'

// ─── Log Analytics Workspace ─────────────────────────────────────────────────

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${prefix}-${environment}'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// ─── Container Apps Environment ──────────────────────────────────────────────

resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: appEnvName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ─── Container Apps Job ───────────────────────────────────────────────────────

resource scraperJob 'Microsoft.App/jobs@2024-03-01' = {
  name: jobName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: containerAppsEnv.id
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 1800   // 30 minutes max per run
      replicaRetryLimit: 1
      scheduleTriggerConfig: {
        // Every Monday at 06:00 UTC
        cronExpression: '0 6 * * 1'
        parallelism: 1
        replicaCompletionCount: 1
      }
      // Secrets pulled from Key Vault via managed identity.
      // The KV Secrets User role for this identity is assigned in main.bicep.
      secrets: [
        {
          name: 'gemini-api-key'
          keyVaultUrl: '${keyVaultUrl}/secrets/gemini-api-key'
          identity: 'system'
        }
        {
          name: 'gmail-app-password'
          keyVaultUrl: '${keyVaultUrl}/secrets/gmail-app-password'
          identity: 'system'
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'scraper'
          image: scraperImageTag
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            {
              name: 'LEGACY_MODE'
              value: 'false'
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
              name: 'STORAGE_ACCOUNT_NAME'
              value: storageAccountName
            }
            {
              name: 'GEMINI_API_KEY'
              secretRef: 'gemini-api-key'
            }
            {
              name: 'GMAIL_APP_PASSWORD'
              secretRef: 'gmail-app-password'
            }
          ]
        }
      ]
    }
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

output jobName string = scraperJob.name
output principalId string = scraperJob.identity.principalId
output containerAppsEnvId string = containerAppsEnv.id
output logAnalyticsWorkspaceId string = logAnalytics.id
