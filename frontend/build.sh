#!/bin/bash
set -euo pipefail

ENV=""
SKIP_DEPLOY=false

while getopts "e:sh" opt; do
  case "$opt" in
    e) ENV="$OPTARG" ;;
    s) SKIP_DEPLOY=true ;;
    h)
      echo "Usage: $0 -e <env> [-s]"
      echo ""
      echo "  -e <env>  Environment (dev|stage|prod)"
      echo "  -s        Skip Terraform deployment"
      echo "  -h        Show this help"
      exit 0
      ;;
    *) exit 1 ;;
  esac
done

if [ -z "$ENV" ]; then
  echo "Error: -e <env> is required"
  exit 1
fi

ENV_FILE=".env.${ENV}"
if [ ! -f "$ENV_FILE" ]; then
  echo "Error: $ENV_FILE not found (copy from $ENV_FILE.example)"
  exit 1
fi

set -a
source "$ENV_FILE"
set +a

npm ci
npm run build

echo ""
echo "Built frontend for env=${ENV} → out/"
echo ""
echo "  API URL:        ${NEXT_PUBLIC_API_URL:-(not set)}"
echo "  Cognito domain: ${NEXT_PUBLIC_COGNITO_DOMAIN:-(not set)}"

if [ "$SKIP_DEPLOY" = false ]; then
  echo ""
  echo "Deploying infrastructure..."
  cd ../terraform
  terraform apply -auto-approve
else
  echo ""
  echo "Skipping terraform deploy."
fi
