// AfDB-Platform — Main Bicep Orchestrator
// Deploys all modules for a given environment (dev | qa | prod)
//
// Usage:
//   az deployment sub create \
//     --location eastus \
//     --template-file infrastructure/main.bicep \
//     --parameters infrastructure/main.parameters.dev.json

targetScope = 'subscription'

// ─── Parameters ───────────────────────────────────────────────────────────────

@description('Deployment environment')
@allowed(['dev', 'qa', 'prod'])
param environment string

@description('Azure region for all resources')
param location string = 'eastus'

@description('Container image for the scraper job (e.g. afdbtrackercr.azurecr.io/afdb-platform:latest)')
param scraperImageTag string

@description('Gemini API key (stored in Key Vault, passed as secure string for initial seeding)')
@secure()
param geminiApiKey string = ''

@description('Gmail app password (stored in Key Vault, passed as secure string for initial seeding)')
@secure()
param gmailAppPassword string = ''

@description('Microsoft Entra External ID tenant ID')
param entraExternalTenantId string = ''

@description('Microsoft Entra External ID client ID for the SPA')
param entraClientId string = ''

// ─── Variables ────────────────────────────────────────────────────────────────

var prefix = 'afdb'
var tags = {
  project: 'afdb-platform'
  environment: environment
  managedBy: 'bicep'
}

// ─── Resource Group ───────────────────────────────────────────────────────────

resource rg 'Microsoft.Resources/resourceGroups@2023-07-01' = {
  name: 'rg-${prefix}-${environment}'
  location: location
  tags: tags
}

// ─── Modules ─────────────────────────────────────────────────────────────────

module keyVault 'modules/keyvault.bicep' = {
  name: 'deploy-keyvault'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    tags: tags
    geminiApiKey: geminiApiKey
    gmailAppPassword: gmailAppPassword
    entraExternalTenantId: entraExternalTenantId
    entraClientId: entraClientId
  }
}

module cosmosDb 'modules/cosmosdb.bicep' = {
  name: 'deploy-cosmosdb'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    tags: tags
  }
}

module storage 'modules/storage.bicep' = {
  name: 'deploy-storage'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    tags: tags
  }
}

module staticWebApp 'modules/staticwebapp.bicep' = {
  name: 'deploy-staticwebapp'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    tags: tags
  }
}

module functions 'modules/functions.bicep' = {
  name: 'deploy-functions'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    tags: tags
    keyVaultName: keyVault.outputs.keyVaultName
    cosmosDbEndpoint: cosmosDb.outputs.endpoint
    cosmosDbDatabaseName: cosmosDb.outputs.databaseName
  }
}

module containerAppJob 'modules/containerapp-job.bicep' = {
  name: 'deploy-containerapp-job'
  scope: rg
  params: {
    prefix: prefix
    environment: environment
    location: location
    tags: tags
    scraperImageTag: scraperImageTag
    keyVaultName: keyVault.outputs.keyVaultName
    cosmosDbEndpoint: cosmosDb.outputs.endpoint
    cosmosDbDatabaseName: cosmosDb.outputs.databaseName
    storageAccountName: storage.outputs.storageAccountName
  }
}

// ─── Role Assignments: Managed Identity → Cosmos DB ──────────────────────────

// Container Apps Job → Cosmos DB Data Contributor
var cosmosDataContributorRoleId = '00000000-0000-0000-0000-000000000002'

resource scraperCosmosRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cosmosDb.outputs.cosmosAccountId, containerAppJob.outputs.principalId, cosmosDataContributorRoleId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cosmosDataContributorRoleId)
    principalId: containerAppJob.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// Azure Functions → Cosmos DB Data Contributor
resource functionsCosmosRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(cosmosDb.outputs.cosmosAccountId, functions.outputs.principalId, cosmosDataContributorRoleId)
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cosmosDataContributorRoleId)
    principalId: functions.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

output resourceGroupName string = rg.name
output cosmosDbEndpoint string = cosmosDb.outputs.endpoint
output staticWebAppUrl string = staticWebApp.outputs.defaultHostname
output functionsUrl string = functions.outputs.defaultHostname
output keyVaultName string = keyVault.outputs.keyVaultName
