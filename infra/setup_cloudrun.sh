#!/usr/bin/env bash
# Create or update the scheduled batch on Cloud Run: a job that runs the batch container,
# and a Cloud Scheduler entry that starts it every 30 minutes. Safe to run again (it updates).
#
#   bash infra/setup_cloudrun.sh <digest-pinned image>
#   e.g. the reference printed by `make image-push`, or by the CI build of main:
#   bash infra/setup_cloudrun.sh asia-southeast1-docker.pkg.dev/<project>/lemon/lemon-batch@sha256:...
#
# Needs: `gcloud auth login` as a project owner, and cloud.env (or cloud.env.ci) for the names.
# The job runs as the existing lemon-batch service account (bucket objectAdmin, registry
# reader), so no key is created or stored anywhere.
set -euo pipefail
cd "$(dirname "$0")/.."

IMAGE_REF="${1:-${IMAGE_REF:-}}"
[ -n "$IMAGE_REF" ] || { echo "usage: bash infra/setup_cloudrun.sh <repo@sha256:... image reference>"; exit 1; }
case "$IMAGE_REF" in
  *@sha256:*) ;;
  *) echo "IMAGE_REF must be digest-pinned (repo@sha256:...), not a tag: $IMAGE_REF"; exit 1 ;;
esac

ENV_FILE=cloud.env
[ -f "$ENV_FILE" ] || ENV_FILE=cloud.env.ci
set -a; . "./$ENV_FILE"; set +a

JOB="${BATCH_JOB:-lemon-batch}"
SCHEDULE_NAME="${BATCH_SCHEDULE_NAME:-lemon-batch-every-30min}"
CRON="${BATCH_CRON:-*/30 * * * *}"
RUN_SA="$IDENTITY_REF"                                   # lemon-batch@<project>
SCHED_SA="lemon-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"
LABELS="course=itcs355,student=${PROJECT_ID},lab=capstone"

gcloud services enable run.googleapis.com cloudscheduler.googleapis.com --project "$PROJECT_ID"

gcloud iam service-accounts describe "$SCHED_SA" --project "$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud iam service-accounts create lemon-scheduler --project "$PROJECT_ID" \
       --display-name="lemon batch scheduler"

# The job pins the image by digest, so a batch can be replayed against the same code and model.
gcloud run jobs deploy "$JOB" --project "$PROJECT_ID" --region "$REGION" \
  --image "$IMAGE_REF" \
  --service-account "$RUN_SA" \
  --command python --args scripts/cloud_batch.py \
  --tasks 1 --max-retries 0 --task-timeout 600 \
  --cpu 2 --memory 2Gi \
  --set-env-vars "CLOUD_PROVIDER=${CLOUD_PROVIDER},PROJECT_ID=${PROJECT_ID},REGION=${REGION},BLOB_URI=${BLOB_URI},CONTAINER_REGISTRY=${CONTAINER_REGISTRY},MODEL_REGISTRY_NAME=${MODEL_REGISTRY_NAME},IDENTITY_REF=${IDENTITY_REF},DATA_DIR=/tmp/data" \
  --labels "$LABELS"

# Only the scheduler's identity may start the job.
gcloud run jobs add-iam-policy-binding "$JOB" --project "$PROJECT_ID" --region "$REGION" \
  --member "serviceAccount:${SCHED_SA}" --role roles/run.invoker >/dev/null

URI="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run"
if gcloud scheduler jobs describe "$SCHEDULE_NAME" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  VERB=update
else
  VERB=create
fi
gcloud scheduler jobs "$VERB" http "$SCHEDULE_NAME" --project "$PROJECT_ID" --location "$REGION" \
  --schedule "$CRON" --time-zone "UTC" \
  --uri "$URI" --http-method POST \
  --oauth-service-account-email "$SCHED_SA"

echo
echo "Cloud Run job:   $JOB   (image $IMAGE_REF)"
echo "Scheduler entry: $SCHEDULE_NAME   ($CRON UTC)   -> $URI"
echo
echo "Try it now:   make run-batch-cloud        (runs the job once and waits for it)"
echo "              make scheduler-run-now      (fires the scheduler entry, as the clock would)"
echo "Stop it:      make scheduler-pause        (resume with make scheduler-resume)"
