#!/usr/bin/env bash
# One-time GCP setup so GitHub Actions can reach the project WITHOUT any stored key.
#
#   bash infra/setup_oidc.sh            # reads cloud.env, needs `gcloud auth login` as project owner
#
# Creates (all idempotent):
#   workload identity pool + GitHub OIDC provider, locked to ONE repo and the main branch
#   service account lemon-publisher   -> may push images (Artifact Registry writer)
#   service account lemon-batch       -> may read/write the data bucket and pull images
# Does NOT reuse anything from the old lab project.
set -euo pipefail
cd "$(dirname "$0")/.."

set -a; . ./cloud.env; set +a
REPO_SLUG="${GITHUB_REPO:-meadowind/ML-Project}"
POOL="lemon-gh-pool"
PROVIDER="github"
BUCKET="$(echo "$BLOB_URI" | sed -E 's#^gs://([^/]+).*#\1#')"
AR_REPO="${CONTAINER_REGISTRY##*/}"
BATCH_SA="lemon-batch@${PROJECT_ID}.iam.gserviceaccount.com"
PUB_SA="lemon-publisher@${PROJECT_ID}.iam.gserviceaccount.com"
NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
LABELS="course=itcs355,student=${PROJECT_ID},lab=capstone"

echo "project=$PROJECT_ID number=$NUMBER repo=$REPO_SLUG bucket=$BUCKET registry_repo=$AR_REPO"

gcloud services enable iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  artifactregistry.googleapis.com --project "$PROJECT_ID"

gcloud iam workload-identity-pools describe "$POOL" --location=global --project "$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud iam workload-identity-pools create "$POOL" --location=global --project "$PROJECT_ID" \
       --display-name="lemon GitHub Actions"

gcloud iam workload-identity-pools providers describe "$PROVIDER" --workload-identity-pool="$POOL" \
  --location=global --project "$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud iam workload-identity-pools providers create-oidc "$PROVIDER" \
       --workload-identity-pool="$POOL" --location=global --project "$PROJECT_ID" \
       --issuer-uri="https://token.actions.githubusercontent.com" \
       --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
       --attribute-condition="assertion.repository=='${REPO_SLUG}' && assertion.ref=='refs/heads/main'"

gcloud iam service-accounts describe "$BATCH_SA" --project "$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud iam service-accounts create lemon-batch --project "$PROJECT_ID" --display-name="lemon batch scorer"
gcloud iam service-accounts describe "$PUB_SA" --project "$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud iam service-accounts create lemon-publisher --project "$PROJECT_ID" --display-name="lemon image publisher"

PRINCIPAL="principalSet://iam.googleapis.com/projects/${NUMBER}/locations/global/workloadIdentityPools/${POOL}/attribute.repository/${REPO_SLUG}"
for SA in "$BATCH_SA" "$PUB_SA"; do
  gcloud iam service-accounts add-iam-policy-binding "$SA" --project "$PROJECT_ID" \
    --role roles/iam.workloadIdentityUser --member "$PRINCIPAL" >/dev/null
done

# least privilege, scoped to the single bucket / repository
gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
  --member "serviceAccount:${BATCH_SA}" --role roles/storage.objectAdmin >/dev/null
gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" --location "$REGION" --project "$PROJECT_ID" \
  --member "serviceAccount:${BATCH_SA}" --role roles/artifactregistry.reader >/dev/null
gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" --location "$REGION" --project "$PROJECT_ID" \
  --member "serviceAccount:${PUB_SA}" --role roles/artifactregistry.writer >/dev/null

echo
echo "Done. Workflow values (already written into .github/workflows/*.yml):"
echo "  WIF_PROVIDER = projects/${NUMBER}/locations/global/workloadIdentityPools/${POOL}/providers/${PROVIDER}"
echo "  BATCH_SA     = ${BATCH_SA}"
echo "  PUBLISHER_SA = ${PUB_SA}"
echo "Check nothing broader is attached:  gcloud projects get-iam-policy ${PROJECT_ID} --flatten=bindings[].members --filter='bindings.members:lemon-' --format='table(bindings.role,bindings.members)'"
