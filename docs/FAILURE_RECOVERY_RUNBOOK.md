# Failure and Recovery Runbook

## 1. Purpose and scope

This runbook describes how to investigate and recover the scheduled
lemon image-classification batch pipeline.

| Resource | Value |
|---|---|
| GCP project | `lemon-mlops-project` |
| Region | `asia-southeast1` |
| Cloud Run Job | `lemon-batch` |
| Cloud Scheduler | `lemon-batch-every-30min` |
| Schedule | Every 30 minutes, UTC |
| Cloud Storage prefix | `gs://lemon-mlops-project-data/lemon/` |

The Cloud Run Job runs `python scripts/cloud_batch.py`.
The process downloads intake data, scores images, and uploads results.
The job is configured with zero automatic retries, so failed executions
require investigation before a recovery attempt.

## 2. Safety rules

- Inspect the failed execution and logs before running the job again.
- Do not repeatedly trigger executions while the cause is unknown.
- Do not use `--reprocess` as the default recovery action. It processes
  every file in `intake/` again and may repeat previous work.
- Do not delete, overwrite, or manually move bucket objects during
  initial diagnosis.
- Do not pause the production scheduler merely to test an alert.
- Never paste credentials, service-account keys, or webhook URLs into
  logs, Git, screenshots, or chat messages.
- If permissions prevent investigation or recovery, ask a project
  administrator for the minimum required access.

## 3. First response: inspect the system

Run these read-only checks first.

### 3.1 Confirm the active GCP account and project

```bash
gcloud auth list
gcloud config get-value project
```

Use the explicit project flag in commands below even if the default
project is different.

### 3.2 Inspect the Cloud Run Job

```bash
gcloud run jobs describe lemon-batch \
  --project=lemon-mlops-project \
  --region=asia-southeast1
```

Check the job configuration and whether the expected job exists.

### 3.3 Inspect recent executions

```bash
gcloud run jobs executions list \
  --job=lemon-batch \
  --project=lemon-mlops-project \
  --region=asia-southeast1 \
  --limit=10
```

Identify the latest execution and whether it completed successfully.
Record the execution name, start time, and status for the incident notes.

### 3.4 Inspect Scheduler state

```bash
gcloud scheduler jobs describe lemon-batch-every-30min \
  --project=lemon-mlops-project \
  --location=asia-southeast1
```

Confirm that the scheduler is enabled and uses the expected schedule.
The configured cron schedule is `*/30 * * * *` in UTC.

## 4. Investigate logs

### 4.1 Read recent batch completion events

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="lemon-batch" AND jsonPayload.event="batch_finished"' \
  --project=lemon-mlops-project \
  --limit=20 \
  --format=json
```

The `batch_finished` event includes `batch_id`, file counts, rejection
rate, low-confidence rate, inspection count, and duration.

### 4.2 Read recent errors

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="lemon-batch" AND severity>=ERROR' \
  --project=lemon-mlops-project \
  --limit=50 \
  --format=json
```

If no useful error appears, inspect the logs for the specific execution
and review its failure status before deciding how to recover.

### 4.3 Check for empty intake

```bash
gcloud logging read \
  'resource.type="cloud_run_job" AND resource.labels.job_name="lemon-batch" AND jsonPayload.event="batch_skipped"' \
  --project=lemon-mlops-project \
  --limit=20 \
  --format=json
```

A `batch_skipped` event caused by an empty intake directory is not
necessarily a failure. The Cloud Run execution can still succeed.
Check whether new input was expected before treating this as an incident.

## 5. Failure scenarios and recovery

### Scenario A: Cloud Run execution failed

1. Inspect recent executions and logs using Sections 3 and 4.
2. Determine which stage failed: `sync_down`, scoring, or `sync_up`.
3. Check the relevant permissions, input data, model/configuration, and
   Cloud Storage availability.
4. Correct the underlying cause before retrying.
5. If the cause is unclear or requires elevated permissions, escalate
   to the project administrator rather than repeatedly rerunning.
6. After the cause is resolved, use the approved execution procedure
   in Section 7.
7. Confirm the new execution succeeded and verify its output in the
   bucket.

The container's working directory defaults to `/tmp/data`. It is
temporary; Cloud Storage is the persistent source of batch artifacts.

### Scenario B: Rejected rate is at least 10%

The configured alert threshold is `rejected_rate >= 0.10`.

1. Open the Cloud Monitoring incident and identify the affected batch.
2. Inspect its `batch_finished` event and batch summary JSON.
3. Review `rejected_samples`, `by_status`, and input images to identify
   recurring causes such as invalid, blurry, or out-of-distribution
   images.
4. Determine whether the rejection is expected input protection or
   indicates an input-quality or pipeline issue.
5. Preserve the original evidence. Do not disable the validation guard
   simply to reduce the rejection rate.
6. Document the cause and any corrective action.

A high rejection rate does not by itself prove that the pipeline failed.

### Scenario C: Low-confidence rate is at least 30%

The configured alert threshold is `low_confidence_rate >= 0.30`.

1. Open the Cloud Monitoring incident and identify the affected batch.
2. Review `low_confidence_count`, `low_confidence_rate`, and
   `needs_inspection_count` in the batch event.
3. Inspect the summary JSON for the confidence histogram and per-status
   breakdown.
4. Check image quality and whether the images are suitable for the
   current model.
5. Route uncertain results for inspection according to the project's
   review process. Do not automatically treat low-confidence predictions
   as confirmed classifications.
6. Record the investigation outcome.

A rate alert is a quality signal; it does not automatically mean that
Cloud Run failed.

### Scenario D: Missed-run alert

The missed-run policy triggers when no successful execution is observed
for more than 60 minutes.

1. Inspect recent Cloud Run executions.
2. Inspect the Scheduler state and schedule.
3. Check Cloud Logging for failed executions and recent batch events.
4. If Scheduler is paused, confirm that resuming it is appropriate and
   that the underlying issue has been addressed.
5. Resume the scheduler only if authorized:

   ```bash
   gcloud scheduler jobs resume lemon-batch-every-30min \
     --project=lemon-mlops-project \
     --location=asia-southeast1
   ```

6. Confirm that Scheduler is enabled.
7. Verify that a subsequent scheduled execution completes successfully
   and produces the expected output.
8. Record the incident time, cause, recovery action, and successful
   execution.

Do not assume that a missing `batch_finished` event alone proves a
missed run. Check the Cloud Run execution status as well.

## 6. Locate batch outputs

List recent batch summary objects:

```bash
gcloud storage ls \
  gs://lemon-mlops-project-data/lemon/summary/
```

After identifying the expected summary object in the listing, copy
its exact object path and inspect it:

```bash
gcloud storage cat 'PASTE_THE_EXACT_SUMMARY_OBJECT_URI_HERE'
```

Replace the placeholder with the complete `gs://...` URI returned by
the listing. Do not guess the filename or assume the object exists.

The summary JSON provides detailed information such as
`confidence_histogram`, `rejected_samples`, and `by_status`, which
are not all included in the `batch_finished` log event.

## 7. Controlled recovery execution

A manual execution can overlap with scheduled work or process input
that has not been fully investigated. Use this only after inspecting
the latest execution, confirming the cause has been addressed, and
obtaining the team's approval.

To start the Cloud Run Job and wait for the execution result:

```bash
gcloud run jobs execute lemon-batch \
  --project=lemon-mlops-project \
  --region=asia-southeast1 \
  --wait
```

Do not add a reprocessing option unless replaying all intake files is
an intentional, reviewed action.

After the command completes:

1. Inspect the execution status.
2. Review its logs.
3. Confirm that the expected summary and result objects are present.
4. Verify the `batch_id` and output correspond to the execution being
   investigated.
5. Confirm that the scheduler remains enabled for subsequent runs.

If the execution fails again, stop retrying and escalate with the
execution name and relevant error logs.

## 8. Alerting and notification limitations

Cloud Monitoring incident creation and external notification delivery
are separate checks.

The project's controlled validation observed Cloud Monitoring
incidents for rejected-rate, low-confidence, and missed-run conditions.
Discord delivery must be tested independently before it can be
considered operational.

Do not report an alert as successfully delivered to Discord based only
on an incident appearing in Cloud Monitoring.

## 9. Incident record

For each incident, record:

- Date and time (UTC)
- Alert policy or observed symptom
- Cloud Run execution name and `batch_id`, if available
- Relevant error message and log evidence
- Root cause, or current investigation status
- Recovery action and who authorized it
- Verification of successful recovery
- Any follow-up work

Do not include secrets or webhook URLs in the incident record.

## 10. Related documentation and evidence

- [Project README](../README.md)
- [Data contract](DATA_CONTRACT.md)
- [Dashboard overview](evidence/11-dashboard-overview.png)
- [Rejected-rate alert evidence](evidence/12-rejected-rate-alert.png)
- [Low-confidence alert evidence](evidence/13-low-confidence-alert.png)
- [Missed-run incident evidence](evidence/14-missed-run-alert-incident.png)
- [Scheduler recovery evidence](evidence/16-scheduler-resume-success.png)
