// AfDB-Platform — Main Bicep Orchestrator
// Deploys the 5 core resources: Key Vault, Cosmos DB, Storage, Static Web App, Functions
//
// The Container Apps scraper job (containerapp-job.bicep) is deployed separately
// via deploy-scraper.bicep once Dynamic VMs quota is granted and a Docker image exists.
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

@description('Region for Azure Static Web Apps (must be one of: westus2, centralus, eastus2, westeurope, eastasia)')
param swaLocation string = 'eastus2'

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
    location: swaLocation   // SWA has limited region support; other resources use 'location'
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

// ─── Role Assignments ─────────────────────────────────────────────────────────

// Cosmos DB data-plane: Functions → Data Contributor
// Uses sqlRoleAssignments (not RBAC) — Cosmos DB data plane is its own role system.
module cosmosRoles 'modules/cosmos-roles.bicep' = {
  name: 'deploy-cosmos-roles'
  scope: rg
  params: {
    cosmosAccountName: cosmosDb.outputs.accountName
    functionsPrincipalId: functions.outputs.principalId
  }
}

// Key Vault Secrets User: Functions → read secrets at runtime
module kvRoles 'modules/kv-roles.bicep' = {
  name: 'deploy-kv-roles'
  scope: rg
  params: {
    keyVaultName: keyVault.outputs.keyVaultName
    functionsPrincipalId: functions.outputs.principalId
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

output resourceGroupName string = rg.name
output cosmosDbEndpoint string = cosmosDb.outputs.endpoint
output staticWebAppUrl string = staticWebApp.outputs.defaultHostname
output functionsUrl string = functions.outputs.defaultHostname
output keyVaultName string = keyVault.outputs.keyVaultName
