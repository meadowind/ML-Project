#!/usr/bin/env bash
# Create the GCP side of this project from scratch (idempotent where gcloud allows it).
#
#   export BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX      # `gcloud billing accounts list`
#   export PROJECT_ID=my-lemon-project               # globally unique
#   export REGION=asia-southeast1
#   export BUDGET_AMOUNT=800THB                      # must match the billing currency
#   bash infra/setup_gcp.sh
#
# Then copy cloud.env.example to cloud.env, fill in the values this script prints, run
# `make cloud-check`, and finally `bash infra/setup_oidc.sh` for GitHub Actions.
# Every resource carries labels course=itcs355,student=<project>,lab=capstone so that
# `make teardown` can find and delete them.
set -euo pipefail

: "${BILLING_ACCOUNT:?set BILLING_ACCOUNT}"
: "${PROJECT_ID:?set PROJECT_ID}"
REGION="${REGION:-asia-southeast1}"
BUDGET_AMOUNT="${BUDGET_AMOUNT:-800THB}"
BUCKET="${PROJECT_ID}-data"
AR_REPO="lemon"
LABELS="course=itcs355,student=${PROJECT_ID},lab=capstone"

gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud projects create "$PROJECT_ID" --labels="$LABELS"
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"

gcloud services enable storage.googleapis.com artifactregistry.googleapis.com \
  billingbudgets.googleapis.com iam.googleapis.com aiplatform.googleapis.com --project "$PROJECT_ID"

gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1 \
  || gcloud storage buckets create "gs://${BUCKET}" --project "$PROJECT_ID" \
       --location "$REGION" --uniform-bucket-level-access
gcloud storage buckets update "gs://${BUCKET}" --update-labels="$LABELS"

gcloud artifacts repositories describe "$AR_REPO" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1 \
  || gcloud artifacts repositories create "$AR_REPO" --project "$PROJECT_ID" --location "$REGION" \
       --repository-format=docker --labels="$LABELS"

gcloud iam service-accounts describe "lemon-batch@${PROJECT_ID}.iam.gserviceaccount.com" --project "$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud iam service-accounts create lemon-batch --project "$PROJECT_ID" --display-name="lemon batch scorer"

# The Vertex AI service agent is created the first time the API is enabled. If these bindings
# fail because the account is not found yet, wait a moment and run the script again.
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
# Vertex AI reads the model files from the bucket when a model is registered.
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com" \
  --role=roles/storage.objectViewer
gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" --project "$PROJECT_ID" --location "$REGION" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-aiplatform.iam.gserviceaccount.com" \
  --role=roles/artifactregistry.reader

# Budget alert. EXCLUDE credits so the alert fires on real spend, not on what credits cover.
gcloud billing budgets create --billing-account="$BILLING_ACCOUNT" --billing-project="$PROJECT_ID" \
  --display-name="${PROJECT_ID}-budget" --budget-amount="$BUDGET_AMOUNT" \
  --filter-projects="projects/${PROJECT_ID}" --filter-credit-treatment=exclude-all-credits \
  --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0 \
  || echo "budget not created (it may already exist: gcloud billing budgets list --billing-account=${BILLING_ACCOUNT})"

cat <<EOF

Put these in cloud.env:
CLOUD_PROVIDER=gcp
PROJECT_ID=${PROJECT_ID}
REGION=${REGION}
BLOB_URI=gs://${BUCKET}/lemon
CONTAINER_REGISTRY=${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}
MLFLOW_TRACKING_URI=sqlite:///mlflow.db
MODEL_REGISTRY_NAME=lemon-leaf-classifier
IDENTITY_REF=lemon-batch@${PROJECT_ID}.iam.gserviceaccount.com
EOF
