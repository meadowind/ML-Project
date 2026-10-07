#!/usr/bin/env bash
# Safe end-to-end test of `make teardown` using THROWAWAY resources.
#
#   bash infra/test_teardown.sh
#
# Creates a scratch bucket (with one object) and a scratch Artifact Registry repo labelled
# lab=teardown-test (NOT lab=capstone), runs the real GcpAdapter.teardown() for that label,
# then checks both are gone and that the real capstone resources were not touched.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; . ./cloud.env; set +a

SUFFIX="$(date +%s)"
BUCKET="${PROJECT_ID}-teardown-test-${SUFFIX}"
REPO="teardown-test-${SUFFIX}"
LABELS="course=itcs355,student=${PROJECT_ID},lab=teardown-test"
REAL_BUCKET="$(echo "$BLOB_URI" | sed -E 's#^gs://([^/]+).*#\1#')"

echo "== create scratch resources"
gcloud storage buckets create "gs://${BUCKET}" --project "$PROJECT_ID" --location "$REGION" --uniform-bucket-level-access
gcloud storage buckets update "gs://${BUCKET}" --update-labels="$LABELS"
echo hello > /tmp/teardown_probe.txt
gcloud storage cp /tmp/teardown_probe.txt "gs://${BUCKET}/probe.txt"
gcloud artifacts repositories create "$REPO" --project "$PROJECT_ID" --location "$REGION" \
  --repository-format=docker --labels="$LABELS"

echo "== run the real adapter teardown for lab=teardown-test"
python -c "
from cloudlayer.factory import get_adapter
from src import config
c = config.load()
deleted = get_adapter(c).teardown(c.tags('teardown-test'))
print('deleted:', deleted)
assert any('${BUCKET}' in d for d in deleted), 'scratch bucket not reported deleted'
assert any('${REPO}' in d for d in deleted), 'scratch repo not reported deleted'
assert not any('${REAL_BUCKET}' == d.removeprefix('gs://') for d in deleted), 'REAL bucket was deleted!'
"

echo "== verify"
if gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1; then echo "FAIL: scratch bucket still exists"; exit 1; fi
if gcloud artifacts repositories describe "$REPO" --project "$PROJECT_ID" --location "$REGION" >/dev/null 2>&1; then
  echo "NOTE: repo still listed (deletion is asynchronous) — re-check in a minute"; else echo "scratch repo gone"; fi
gcloud storage buckets describe "gs://${REAL_BUCKET}" --format='value(name)' >/dev/null && echo "real bucket intact: ${REAL_BUCKET}"
echo "TEARDOWN TEST PASSED"
