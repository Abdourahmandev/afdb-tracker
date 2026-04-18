#!/bin/bash
# AfDB-Platform — One-command Bicep deployment
# Usage: ./infrastructure/scripts/deploy.sh dev
#        ./infrastructure/scripts/deploy.sh qa
#        ./infrastructure/scripts/deploy.sh prod

set -euo pipefail

ENVIRONMENT="${1:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INFRA_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PARAMS_FILE="${INFRA_DIR}/main.parameters.${ENVIRONMENT}.json"
TEMPLATE_FILE="${INFRA_DIR}/main.bicep"

if [[ ! "$ENVIRONMENT" =~ ^(dev|qa|prod)$ ]]; then
  echo "ERROR: Environment must be dev, qa, or prod. Got: $ENVIRONMENT"
  exit 1
fi

if [[ ! -f "$PARAMS_FILE" ]]; then
  echo "ERROR: Parameters file not found: $PARAMS_FILE"
  exit 1
fi

echo "=== AfDB-Platform Deployment ==="
echo "Environment : $ENVIRONMENT"
echo "Template    : $TEMPLATE_FILE"
echo "Parameters  : $PARAMS_FILE"
echo ""

# Step 1: Bicep lint
echo "[1/4] Linting Bicep..."
az bicep build --file "$TEMPLATE_FILE"
echo "      Lint OK"

# Step 2: What-if (dry run)
echo "[2/4] Running what-if (dry run)..."
az deployment sub what-if \
  --location eastus \
  --template-file "$TEMPLATE_FILE" \
  --parameters "$PARAMS_FILE" \
  --output table

# Confirm before deploying to qa or prod
if [[ "$ENVIRONMENT" != "dev" ]]; then
  echo ""
  read -r -p "Deploy to $ENVIRONMENT? (yes/no): " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Deployment cancelled."
    exit 0
  fi
fi

# Step 3: Deploy
echo "[3/4] Deploying to $ENVIRONMENT..."
DEPLOYMENT_NAME="afdb-platform-${ENVIRONMENT}-$(date +%Y%m%d%H%M%S)"

az deployment sub create \
  --name "$DEPLOYMENT_NAME" \
  --location eastus \
  --template-file "$TEMPLATE_FILE" \
  --parameters "$PARAMS_FILE" \
  --output table

# Step 4: Print outputs
echo "[4/4] Deployment outputs:"
az deployment sub show \
  --name "$DEPLOYMENT_NAME" \
  --query "properties.outputs" \
  --output table

echo ""
echo "=== Deployment complete: $ENVIRONMENT ==="
