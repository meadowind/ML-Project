# Cloud configuration snapshot (exported before teardown)

Exported on 17 October 2026 (Asia/Bangkok) from project `lemon-mlops-project`, region `asia-southeast1`, so the
deployment can be recreated after the cloud resources are deleted. These are the configurations as they were running;
they contain no passwords or keys. Personal email addresses were replaced with `<redacted>`. Notification channels
were not exported because they hold an email address; create one and attach it to the policies (see below).

| File | Command used | What it records |
| --- | --- | --- |
| `alert-policies.json` | `gcloud monitoring policies list --format=json` | The three alert policies: conditions, thresholds, `autoClose: 1800s`, `notificationPrompts` OPENED and CLOSED |
| `log-based-metrics.json` | `gcloud logging metrics list --format=json` | `lemon-batch-rejected-rate`, `lemon-batch-low-confidence-rate`, `lemon-batch-duration-seconds` |
| `dashboards.json` | `gcloud monitoring dashboards list --format=json` | The `lemon-batch-monitoring` dashboard |
| `cloud-run-job.yaml` | `gcloud run jobs describe lemon-batch --format=export` | Image digest, environment, 2 vCPU / 2 GiB, 600 s timeout, no retries |
| `scheduler-job.json` | `gcloud scheduler jobs describe lemon-batch-every-30min --format=json` | Schedule `0 */2 * * *`, `Asia/Bangkok`, target and service account |

## How to recreate from these files

The supported way to recreate the job and scheduler is `infra/setup_cloudrun.sh` (README, "The scheduled batch"). The
files here record what it produced. The monitoring steps below have not been tested.

1. **Log-based metrics.** For each entry in `log-based-metrics.json`, save it as its own file, remove `createTime`
   and `updateTime`, and run `gcloud logging metrics create <name> --config-from-file=<file>`. Create the metrics first,
   because the alert policies and the dashboard refer to them.
2. **Notification channel.** Create an email channel in Cloud Monitoring and note its id.
3. **Alert policies.** For each policy in `alert-policies.json`, remove the output-only fields (`name`, `creationRecord`,
   `mutationRecord`), replace `notificationChannels` with the new channel, and run
   `gcloud monitoring policies create --policy-from-file=<file>`.
4. **Dashboard.** Remove `name` and `etag` from the entry in `dashboards.json` and run
   `gcloud monitoring dashboards create --config-from-file=<file>`.

The thresholds are written as `0.099999` and `0.299999` because the condition uses `COMPARISON_GT`; they mean 10% and 30%
(README, "Alert policies").
