// Azure Blob Storage — Legacy report.html hosting + future use
// Preserves the existing afdbtracker4990 storage account pattern for legacy pipeline

param prefix string
param environment string
param location string
param tags object

// Globally unique name per environment — 24 char max, lowercase alphanumeric only
var storageAccountName = 'stafdb${environment}${take(uniqueString(resourceGroup().id), 8)}'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: take(storageAccountName, 24)
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: true    // Required for static website hosting
    supportsHttpsTrafficOnly: true
    staticWebsite: {
      enabled: true
      indexDocument: 'index.html'
      errorDocument404Path: 'index.html'
    }
  }
}

// $web container (static website)
resource webContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  name: '${storageAccount.name}/default/$web'
  properties: {
    publicAccess: 'Blob'
  }
}

// afdb-data file share (legacy DuckDB persistence)
resource dataFileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-05-01' = {
  name: '${storageAccount.name}/default/afdb-data'
  properties: {
    shareQuota: 5   // 5 GB — sufficient for DuckDB file
    enabledProtocols: 'SMB'
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

output storageAccountId string = storageAccount.id
output storageAccountName string = storageAccount.name
output primaryEndpoint string = storageAccount.properties.primaryEndpoints.web
