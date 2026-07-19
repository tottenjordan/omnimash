#!/bin/bash
set -euo pipefail

# ==============================================================================
# OmniMash GCS Bucket Provisioning Script
# Idempotently creates the GCS bucket specified in .env or settings
# ==============================================================================

# Load .env if present
if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-hybrid-vertex}"
REGION="${GOOGLE_CLOUD_REGION:-us-central1}"
BUCKET_NAME="${OMNIMASH_GCS_BUCKET:-omnimash-media-934903580331}"

echo "=========================================================="
echo "🎬 OmniMash GCS Bucket Provisioning"
echo "Project:  ${PROJECT_ID}"
echo "Region:   ${REGION}"
echo "Bucket:   gs://${BUCKET_NAME}"
echo "=========================================================="

if gcloud storage buckets describe "gs://${BUCKET_NAME}" &>/dev/null; then
  echo "✅ Bucket gs://${BUCKET_NAME} already exists."
else
  echo "📦 Creating bucket gs://${BUCKET_NAME} in region ${REGION}..."
  gcloud storage buckets create "gs://${BUCKET_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --uniform-bucket-level-access
  echo "✅ Bucket gs://${BUCKET_NAME} created successfully."
fi
