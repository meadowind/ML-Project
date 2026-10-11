# MLOps Cost Report

## 1. Report Scope

- GCP project: `lemon-mlops-project`
- Region: `asia-southeast1`
- Cloud Run Job: `lemon-batch`
- Billing export period: 1–11 October 2026
- Billing export snapshot: 11 October 2026, 14:55 ICT
- Cloud Run executions covered by the reported execution count: 135
- Execution window: 8 October 2026, 13:30 UTC to 11 October 2026, 07:30 UTC
- Purpose: Summarize observed project costs and explain why a validated cost per scored prediction is not reported.

The billing figures are from the export available at the snapshot time and may change as additional usage is recorded. The billing period and the execution-count window are not identical, so per-prediction ratios are indicative rather than fully aligned unit costs.

## 2. Batch Processing Summary

The supplied billing snapshot includes 135 Cloud Run executions for the period 8 October 2026, 13:30 UTC to 11 October 2026, 07:30 UTC.

A current, aligned count of completed batches and scored predictions is not established by this billing snapshot. Therefore, this report does not carry forward earlier batch or prediction counts as the denominator for a cost-per-prediction calculation.

Scheduled executions can occur without new photos, so execution count and scored-prediction count represent different measures of workload.

## 3. Billing Export Breakdown

| Billing item | Reported cost (THB) | Cost behavior |
|---|---:|---|
| Cloud Run Jobs CPU | 10.54 | Execution-dependent |
| Cloud Run Jobs Memory | 1.17 | Execution-dependent |
| Artifact Registry network internet egress | 5.35 | One-off usage observed in this period |
| Artifact Registry storage | 1.57 | Recurring storage |
| Vertex AI training / pipelines N1 Core | 0.71 | Training-related; incurred during the observed period |
| Vertex AI training / pipelines N1 RAM | 0.36 | Training-related; incurred during the observed period |
| Vertex AI training SSD persistent disk | 0.06 | Training-related storage |
| Other listed services and adjustments | 0.00 (rounded) | No material charge shown |
| **Total reported project cost** | **19.77** | |

The total is the billing export subtotal. Individual rows are rounded for display.

The export does not separately establish the amount of Free Trial credits applied or the final payable amount. Therefore, THB 19.77 is the reported subtotal, not a claim about the final amount payable after credits.

## 4. Cloud Run Cost per Execution

Cloud Run charges in the supplied billing export are:

- CPU: THB 10.54
- Memory: THB 1.17
- Combined Cloud Run total: THB 11.71

Using 135 executions:

`THB 11.71 / 135 = approximately THB 0.087 per execution`

The CPU component averages approximately THB 0.078 per execution, and memory averages approximately THB 0.009 per execution.

This is a list-price average of billed Cloud Run CPU and memory per execution. The Cloud Run free tier and Free Trial credits are not applied. At 48 scheduled runs per day (one every 30 minutes), the estimated cost is approximately THB 4.20 per day.

The billing export records 14,520 CPU-seconds at 2 vCPU. This corresponds to approximately 54 billed seconds per execution when divided by 135 executions and 2 vCPU. This is a billed average derived from aggregate usage, not a measured individual execution duration. Console-observed execution durations were approximately 12–40 seconds.

## 5. Fixed and Variable Cost View

### Execution-dependent costs

Cloud Run CPU and memory charges vary with billed resource usage. For the observed period, these charges totalled THB 11.71 across 135 executions, or approximately THB 0.087 per execution on average.

The job is scheduled every 30 minutes whether or not new photos are available. Executions that find no new files can still contribute to operating costs without increasing the scored-prediction count.

### Recurring or capacity-related costs

Artifact Registry storage was THB 1.57 in the supplied export. Storage costs can recur while images remain stored, independent of how many predictions are scored during a particular execution.

### One-off or workload-specific costs

Artifact Registry internet egress was THB 5.35 for 1.33 GiB. The team reports that this usage came from GitHub Actions runners pulling the container image before the workflow moved to Cloud Scheduler. The recorded egress amount has remained unchanged since 9 October, and this transfer is understood to have stopped after the migration.

Vertex AI training-related charges totalled THB 1.13 for CPU, RAM, and SSD-backed persistent disk. These charges arose from training activity in the observed period and should not be treated as a recurring per-inference cost without further evidence.

This classification describes the observed usage and expected cost behavior; it does not imply that every charge is strictly fixed or that future usage will be identical.

## 6. Cost per 1,000 Scored Predictions

Per-1,000-photo costs are not reported as validated unit costs in this snapshot. The available execution count and billing data do not establish a sufficiently aligned, verified prediction denominator. Cloud Run costs include scheduled-run overhead, including executions that may not score any photos.

## 7. Interpretation and Limitations

1. The billing export covers 1–11 October 2026 at the snapshot taken on 11 October 2026, 14:55 ICT. The 135-execution count covers 8 October 2026, 13:30 UTC to 11 October 2026, 07:30 UTC; these periods are not fully aligned.
2. Cloud Run CPU and memory total THB 11.71 over 135 executions, approximately THB 0.087 per execution before applying the free tier or Free Trial credits.
3. The export records 14,520 vCPU-seconds over 135 executions at 2 vCPU, equivalent to approximately 54 billed seconds per execution. This is an aggregate billed-time average, not a measured individual runtime. Console-observed durations were approximately 12–40 seconds, and the gap is not fully explained.
4. At 48 scheduled runs per day, Cloud Run CPU and memory cost is approximately THB 4.20 per day at list price, before free-tier usage or credits.
5. Cloud Run costs are largely run-related overhead. Runs that find no new photos can still incur cost without scoring photos, so per-1,000-photo figures should not be presented as validated unit costs.
6. Artifact Registry egress was THB 5.35 for 1.33 GiB and is attributed to CI image pulls before the move to Cloud Scheduler. The amount did not increase between the reported exports.
7. Artifact Registry storage was THB 1.57. Vertex AI training-related CPU, RAM, and SSD charges totalled THB 1.13 and should be distinguished from inference operating costs.
8. The reported THB 19.77 is the billing export total; it does not establish the final amount payable after any Free Trial credits.

## 8. Official Pricing References

- [Cloud Run pricing](https://cloud.google.com/run/pricing)
- [Artifact Registry pricing](https://cloud.google.com/artifact-registry/pricing)
- [Vertex AI pricing](https://cloud.google.com/vertex-ai/pricing)

These links are official pricing references. The reported THB values in this document come from the project's supplied billing export, not from an independent recalculation of list prices.

## 9. Recommended Follow-up

- Re-export billing data after the reporting period or at a clearly recorded cutoff time.
- Align the billing cutoff with the Cloud Logging window used to count scored predictions.
- Track Cloud Run CPU and memory separately from image transfer, storage, and Vertex AI training.
- Recalculate cost per 1,000 scored predictions after collecting aligned billing data and a verified scored-prediction count over the same period.
- Record the export timestamp and the exact log-query window whenever this report is updated.

## 10. Data Sources

- Google Cloud Billing export for 1–11 October 2026, snapshot taken 11 October 2026 at 14:55 ICT.
- Cloud Run execution count of 135 for the period 8 October 2026, 13:30 UTC to 11 October 2026, 07:30 UTC.
- Cloud Logging query for `resource.type="cloud_run_job"` and `resource.labels.job_name="lemon-batch"`.
- Batch summary logs containing `batch_finished` events.
