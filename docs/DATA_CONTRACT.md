# Data contract: what the batch job produces (for monitoring and alerting)

Everything lives under one prefix in the project bucket: `gs://<project>-data/lemon/`
(`BLOB_URI` in `cloud.env`). Nothing below is ever modified after it is written.

| Prefix | Content | One object per |
|---|---|---|
| `intake/` | photos uploaded by growers (input, never touched by the job) | photo |
| `archive/` | copy of every photo that was **scored** | photo |
| `quarantine/` | copy of every photo that was **rejected** or crashed the scorer | photo |
| `results/<batch_id>.csv` | one row per photo in the batch | batch |
| `summary/<batch_id>.json` | batch-level numbers (below) | batch |
| `logs/<batch_id>.jsonl` | one JSON event per line | batch |

`batch_id` looks like `batch-20261007T133147Z` (UTC start time) and appears in every row, summary and log line.

**A run with no new photos writes nothing** (no summary, no log in the bucket): the job logs
`batch_skipped` to its own output (Cloud Logging) and exits. So "no summary for a while" means "no new
photos", not "the job is broken". To check that the schedule itself is alive, look at the executions of
the Cloud Run job `lemon-batch` (`gcloud run jobs executions list --job lemon-batch --region
asia-southeast1`) or at the Cloud Scheduler entry `lemon-batch-every-30min`: an execution exists every 30
minutes whether or not any photo was scored.

## `summary/<batch_id>.json`
```json
{
  "batch_id": "batch-20261007T133147Z",
  "finished_at": "2026-10-07T13:31:50Z",
  "model_version": "v2.1.0",
  "files_total": 7,
  "files_scored": 7,
  "files_rejected": 0,
  "rejected_rate": 0.0,
  "low_confidence_threshold": 0.6,
  "low_confidence_count": 0,
  "low_confidence_rate": 0.0,
  "needs_inspection_count": 3,
  "by_status": {"SCORED": 7},
  "rejected_samples": [{"filename": "blurred_leaf.jpg", "status": "REJECTED_BLURRED"}],
  "confidence_histogram": {"0.0-0.1": 0, "0.1-0.2": 0, "...": 0, "0.9-1.0": 7},
  "duration_seconds": 2.85
}
```
- `rejected_rate` = `files_rejected / files_total` (0 when the batch is empty).
- `low_confidence_rate` = `low_confidence_count / files_scored` — the denominator is **scored** files only, because a rejected file has no confidence.
- `rejected_samples`: up to 5 rejected files, sorted by name, for naming examples in an alert. Includes `ERROR_UNEXPECTED`.
- `confidence_histogram`: scored files only, ten bins of width 0.1 (all ten keys always present; a confidence of exactly 1.0 counts in `0.9-1.0`). The counts sum to `files_scored`.
- `needs_inspection_count`: scored files whose predicted class is not `Healthy_Leaf` or whose confidence is below 0.6 (a "Healthy" the model is unsure about is flagged too).

## `results/<batch_id>.csv`
Columns, in order: `batch_id, filename, status, predicted_class, confidence, needs_inspection,
model_version, blur_score, foliage_ratio, rejection_reason, processed_at`.
`needs_inspection` is the text `true` or `false`. For rejected rows `predicted_class` and `confidence` are empty.

`status` is one of: `SCORED`, `REJECTED_BLURRED`, `REJECTED_OOD_NON_LEAF`, `REJECTED_RESOLUTION`,
`REJECTED_CORRUPTED`, `ERROR_UNEXPECTED`.

## `logs/<batch_id>.jsonl`
Events (`event` field): `batch_started`, `model_loaded`, `file_scored`, `file_rejected`, `file_error`,
`batch_finished` (carries the summary numbers), `batch_skipped` (job output only, never uploaded).
Every line has `ts` and `batch_id`. Every event is also printed to the job's standard output, so it appears
in Cloud Logging under the Cloud Run job `lemon-batch`, including `batch_skipped`.

## Alert rules from the proposal (initial thresholds)
- fire when `rejected_rate >= 0.10` **or** `low_confidence_rate >= 0.30`;
- the message names the `batch_id`, the error count (`files_rejected`) and sample filenames (`rejected_samples`);
- **missed run** (a health signal, not a data signal): no successful execution of the Cloud Run job
  `lemon-batch` for about 45–60 minutes. It must be based on job executions, not on summaries, because a
  run with no new photos writes none.

Known limit worth showing on the dashboard: the classifier is often **confident on non-leaf photos**
(see README, "The failure we designed for"), which is why a confidence alert alone is not enough and
the input validator exists; it also means `low_confidence_rate` stays low for photos that are not leaves.
