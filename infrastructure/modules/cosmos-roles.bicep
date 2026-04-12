// Cosmos DB data-plane role assignments
// Uses sqlRoleAssignments (not Microsoft.Authorization/roleAssignments)
// because Cosmos DB data-plane access uses its own built-in role system.
//
// Built-in role IDs:
//   00000000-0000-0000-0000-000000000001 = Cosmos DB Built-in Data Reader
//   00000000-0000-0000-0000-000000000002 = Cosmos DB Built-in Data Contributor

param cosmosAccountName string
param functionsPrincipalId string
@description('Container Apps Job principal ID. Leave empty to skip scraper role assignment.')
param scraperPrincipalId string = ''

var dataContributorRoleId = '00000000-0000-0000-0000-000000000002'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-02-15-preview' existing = {
  name: cosmosAccountName
}

resource scraperRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-02-15-preview' = if (!empty(scraperPrincipalId)) {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, empty(scraperPrincipalId) ? 'placeholder' : scraperPrincipalId, dataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${dataContributorRoleId}'
    principalId: scraperPrincipalId
    scope: cosmosAccount.id
  }
}

resource functionsRole 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-02-15-preview' = {
  parent: cosmosAccount
  name: guid(cosmosAccount.id, functionsPrincipalId, dataContributorRoleId)
  properties: {
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/${dataContributorRoleId}'
    principalId: functionsPrincipalId
    scope: cosmosAccount.id
  }
}
