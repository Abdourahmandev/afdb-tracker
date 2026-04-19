// Alert Rule — Pipeline Job Failure
// Sends an email when the weekly Container Apps Job exits with an error.
// Queries Log Analytics for error-level log entries from the scraper job.

param prefix string
param environment string
param location string
param tags object
param alertEmail string
param logAnalyticsWorkspaceId string

// ─── Action Group ────────────────────────────────────────────────────────────

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: 'ag-${prefix}-${environment}-pipeline'
  location: 'global'
  tags: tags
  properties: {
    groupShortName: 'pipeline'
    enabled: true
    emailReceivers: [
      {
        name: 'pipeline-alert-email'
        emailAddress: alertEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

// ─── Scheduled Query Rule ────────────────────────────────────────────────────
// Evaluates every hour; alerts if the job produced any error/exception lines
// in the last hour. Severity 2 = Warning.

// AzureActivity is always present and captures ARM-level Container Apps Job execution results.
// ContainerApp log tables (ContainerAppSystemLogs_CL etc.) are lazily created on first run
// and cannot be validated at deploy time. AzureActivity is reliable from day 0.
var failureQuery = 'AzureActivity | where ResourceGroup =~ "rg-${prefix}-${environment}" | where OperationNameValue =~ "MICROSOFT.APP/JOBS/RUNS/WRITE" | where ActivityStatusValue =~ "Failure" | where TimeGenerated > ago(2h) | count'

resource pipelineFailureAlert 'Microsoft.Insights/scheduledQueryRules@2022-06-15' = {
  name: 'alert-pipeline-${environment}-failure'
  location: location
  tags: tags
  properties: {
    displayName: '[${environment}] Pipeline Job Failure'
    description: 'Fires when the weekly scraper job logs an error or exception'
    enabled: true
    skipQueryValidation: true   // Log tables are created lazily on first Container Apps run
    scopes: [logAnalyticsWorkspaceId]
    evaluationFrequency: 'PT1H'
    windowSize: 'PT1H'
    severity: 2
    criteria: {
      allOf: [
        {
          query: failureQuery
          timeAggregation: 'Count'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [actionGroup.id]
    }
  }
}

// ─── Outputs ─────────────────────────────────────────────────────────────────

output actionGroupId string = actionGroup.id
output alertRuleId string = pipelineFailureAlert.id
