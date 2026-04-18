// Azure Static Web Apps — Frontend (Free Tier)
// Hosts the AfDB-Platform user dashboard and registration flow

param prefix string
param environment string
param location string
param tags object

var swaName = 'swa-${prefix}-${environment}'

// Static Web Apps free tier supports global CDN, custom domains, preview envs
resource staticWebApp 'Microsoft.Web/staticSites@2023-12-01' = {
  name: swaName
  location: location   // Limited to specific regions; eastus2 and westus2 recommended
  tags: tags
  sku: {
    name: 'Free'
    tier: 'Free'
  }
  properties: {
    // Repository settings are configured post-deploy via GitHub Actions
    // or Azure Portal. Left empty here for IaC-only provisioning.
    stagingEnvironmentPolicy: 'Enabled'   // Allow preview environments for PRs
    allowConfigFileUpdates: true
    enterpriseGradeCdnStatus: 'Disabled'  // Free tier limitation
  }
}

// App settings (non-secret configuration)
// Secrets should come from Key Vault references, not direct values
resource swaAppSettings 'Microsoft.Web/staticSites/config@2023-12-01' = {
  parent: staticWebApp
  name: 'appsettings'
  properties: {
    ENVIRONMENT: environment
    API_BASE_URL: 'https://func-${prefix}-${environment}.azurewebsites.net'
    // Entra External ID — non-secret config
    // ENTRA_TENANT_ID and ENTRA_CLIENT_ID set post-deploy after Entra tenant is created
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

output staticWebAppId string = staticWebApp.id
output defaultHostname string = staticWebApp.properties.defaultHostname
output deploymentToken string = staticWebApp.listSecrets().properties.apiKey
