#!/usr/bin/env bash
set -e

PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-"hybrid-vertex"}
REGION=${GOOGLE_CLOUD_REGION:-"us-central1"}
SERVICE_NAME="omnimash"

echo "=========================================================="
echo "🚀 Deploying OmniMash Full-Stack Application to Cloud Run"
echo "   Project: $PROJECT_ID"
echo "   Region:  $REGION"
echo "   Service: $SERVICE_NAME"
echo "=========================================================="

# Build environment variables list from .env if it exists
ENV_ARGS=()
if [ -f .env ]; then
  ENV_VARS=$(grep -v '^#' .env | grep '=' | grep -v '^PORT=' | tr '\n' ',' | sed 's/,$//')
  if [ -n "$ENV_VARS" ]; then
    ENV_ARGS=(--set-env-vars "$ENV_VARS,PYTHONPATH=/app/src")
  fi
else
  ENV_ARGS=(--set-env-vars GOOGLE_CLOUD_PROJECT="$PROJECT_ID",GOOGLE_CLOUD_LOCATION="$REGION",GEMINI_LOCATION="global",PYTHONPATH="/app/src")
fi

gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 2Gi \
  --cpu 2 \
  "${ENV_ARGS[@]}"

echo ""
echo "✅ Deployment command submitted to Cloud Run!"
