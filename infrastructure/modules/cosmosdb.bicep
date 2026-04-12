// Azure Cosmos DB for NoSQL — Free Tier
// Containers: jobs (partition: source_id), users (partition: /id), evaluations (partition: /user_id)
// Vector index on jobs.embedding (DiskANN, cosine similarity)

param prefix string
param environment string
param location string
param tags object

var accountName = 'cosmos-${prefix}-${environment}'
var databaseName = 'afdb-platform'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-02-15-preview' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    // Free tier — one per subscription
    enableFreeTier: environment == 'dev'
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      { name: 'EnableNoSQLVectorSearch' }  // Enable vector search (preview)
    ]
    disableLocalAuth: false   // Allow connection string for local dev; set true in prod
    publicNetworkAccess: environment == 'prod' ? 'Disabled' : 'Enabled'
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-02-15-preview' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
    options: {
      // Shared throughput at database level — shared across all containers
      // 1000 RU/s is the free tier minimum
      throughput: 1000
    }
  }
}

// ─── jobs container ──────────────────────────────────────────────────────────
// Partition key: /source_id — enables efficient cross-user reads per source
// Vector index on /embedding — DiskANN for fast approximate nearest-neighbor

resource jobsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: database
  name: 'jobs'
  properties: {
    resource: {
      id: 'jobs'
      partitionKey: {
        paths: ['/source_id']
        kind: 'Hash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          { path: '/source_id/?' }
          { path: '/scraped_at/?' }
          { path: '/deadline/?' }
        ]
        excludedPaths: [
          { path: '/description_raw/?' }  // Exclude large text field
          { path: '/embedding/*' }         // Vector path excluded from regular index
          { path: '/"_etag"/?' }
        ]
        vectorIndexes: [
          {
            path: '/embedding'
            type: 'diskANN'
          }
        ]
      }
      vectorEmbeddingPolicy: {
        vectorEmbeddings: [
          {
            path: '/embedding'
            dataType: 'float32'
            distanceFunction: 'cosine'
            dimensions: 768   // Gemini text-embedding-004 output dimensions
          }
        ]
      }
    }
  }
}

// ─── users container ─────────────────────────────────────────────────────────
// Partition key: /id — user_id is unique per user

resource usersContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: database
  name: 'users'
  properties: {
    resource: {
      id: 'users'
      partitionKey: {
        paths: ['/id']
        kind: 'Hash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          { path: '/email/?' }
          { path: '/verified/?' }
          { path: '/enabled_sources/*' }
        ]
        excludedPaths: [
          { path: '/profile_text/?' }
          { path: '/"_etag"/?' }
        ]
      }
    }
  }
}

// ─── evaluations container ───────────────────────────────────────────────────
// Partition key: /user_id — all evaluations for a user land in same partition

resource evaluationsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-02-15-preview' = {
  parent: database
  name: 'evaluations'
  properties: {
    resource: {
      id: 'evaluations'
      partitionKey: {
        paths: ['/user_id']
        kind: 'Hash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          { path: '/user_id/?' }
          { path: '/job_id/?' }
          { path: '/source_id/?' }
          { path: '/score/?' }
          { path: '/email_sent/?' }
          { path: '/evaluated_at/?' }
        ]
        excludedPaths: [
          { path: '/summary/?' }
          { path: '/"_etag"/?' }
        ]
      }
    }
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

output cosmosAccountId string = cosmosAccount.id
output endpoint string = cosmosAccount.properties.documentEndpoint
output databaseName string = databaseName
output accountName string = accountName
