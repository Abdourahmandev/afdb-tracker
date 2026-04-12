// Azure Container Apps Job — Weekly Scraper
// Consumption plan (pay-per-use), system-assigned managed identity
// Runs all enabled scrapers on a weekly CRON schedule

param prefix string
param environment string
param location string
param tags object
param scraperImageTag string
param keyVaultName string
param cosmosDbEndpoint string
param cosmosDbDatabaseName string
param storageAccountName string

var appEnvName = 'cae-${prefix}-${environment}'
var jobName = 'ca-job-${prefix}-${environment}'

// ─── Container Apps Environment ──────────────────────────────────────────────

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
        // Every Monday at 08:00 UTC
        cronExpression: '0 8 * * MON'
        parallelism: 1
        replicaCompletionCount: 1
      }
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
              // Gemini API key from Key Vault via managed identity
              name: 'GEMINI_API_KEY'
              secretRef: 'gemini-api-key'
            }
            {
              name: 'GMAIL_APP_PASSWORD'
              secretRef: 'gmail-app-password'
            }
            {
              name: 'SCORE_THRESHOLD'
              value: '7'
            }
          ]
        }
      ]
      // Secrets reference Key Vault via managed identity
      // Requires Key Vault access policy for the job's principal ID (set after deploy)
    }
  }
}

// ─── Key Vault Access Policy for Managed Identity ───────────────────────────
// Note: Role assignment to Key Vault is done in main.bicep to avoid circular deps

// ─── Outputs ─────────────────────────────────────────────────────────────────

output jobName string = scraperJob.name
output principalId string = scraperJob.identity.principalId
output containerAppsEnvId string = containerAppsEnv.id
