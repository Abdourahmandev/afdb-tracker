// Key Vault RBAC role assignments — Key Vault Secrets User
// Required for managed identities to read secrets at runtime.
//
// Key Vault Secrets User role ID: 4633458b-17de-408a-b874-0445c86b69e0
// This is an Azure built-in RBAC role (control plane), valid for KV with
// enableRbacAuthorization: true.

param keyVaultName string
param functionsPrincipalId string
@description('Container Apps Job principal ID. Leave empty to skip scraper role assignment.')
param scraperPrincipalId string = ''

var kvSecretsUserRoleId = '4633458b-17de-408a-b874-0445c86b69e0'

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: keyVaultName
}

resource funcKvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVault.id, functionsPrincipalId, kvSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
    principalId: functionsPrincipalId
    principalType: 'ServicePrincipal'
  }
}

resource scraperKvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(scraperPrincipalId)) {
  name: guid(keyVault.id, empty(scraperPrincipalId) ? 'placeholder' : scraperPrincipalId, kvSecretsUserRoleId)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', kvSecretsUserRoleId)
    principalId: scraperPrincipalId
    principalType: 'ServicePrincipal'
  }
}
