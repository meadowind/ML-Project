# MLOps Cost Report

## 1. Report Scope

- GCP project: `lemon-mlops-project`
- Region: `asia-southeast1`
- Cloud Run Job: `lemon-batch`
- Billing export selection: 1–31 October 2026
- Cloud Logging query window: 1–31 October 2026 (UTC)
- Purpose: Estimate Cloud Run operating cost and overall reported project cost per 1,000 scored predictions.

The billing date range is the selected export window, not a finalized full-month bill. The values below reflect the export currently available and may change as additional usage is recorded.

## 2. Batch Processing Summary

The Cloud Logging query returned the following completed-batch summary:

| Metric | Value |
|---|---:|
| Completed batches (`batch_finished`) | 6 |
| Files total | 21 |
| Files scored | 17 |
| Files rejected | 4 |
| Rejection rate among total files | 19.05% |

The rejection rate is calculated as `4 / 21 × 100`.

`batch_skipped` events represent scheduled executions that found no new files. They are relevant to operational overhead even though they do not contribute scored predictions.

## 3. Billing Export Breakdown

| Billing item | Reported cost (THB) |
|---|---:|
| Cloud Run Jobs CPU | 2.09 |
| Cloud Run Jobs Memory | 0.23 |
| Artifact Registry network internet egress | 5.35 |
| Artifact Registry storage | 0.02 |
| Vertex AI training / pipelines N1 Core | 0.71 |
| Vertex AI training / pipelines N1 RAM | 0.36 |
| Vertex AI training SSD persistent disk | 0.06 |
| Other listed services and adjustments | 0.00 (rounded in export) |
| **Billing export subtotal** | **8.83** |

The subtotal is taken from the billing export. Individual displayed rows may be rounded, so their displayed values may not sum exactly to the export subtotal.

The export does not show Free Trial credits as a separate line item. Therefore, this report does not claim that THB 8.83 is the final amount payable after credits.

## 4. Cost per 1,000 Scored Predictions

### Cloud Run CPU and memory cost

Cloud Run CPU and memory charges total:

`THB 2.09 + THB 0.23 = THB 2.32`

Using 17 scored predictions as the denominator:

`THB 2.32 / 17 × 1,000 = THB 136.47`

**Provisional estimate: THB 136.47 per 1,000 scored predictions.**

This is an observed average for the current workload, not a guaranteed marginal cost for future predictions. The Cloud Run charges may include scheduled executions that found no new files.

### Total reported project cost

Using the billing export subtotal:

`THB 8.83 / 17 × 1,000 = THB 519.41`

**Provisional estimate: THB 519.41 per 1,000 scored predictions.**

This broader figure includes reported Artifact Registry and Vertex AI training costs, in addition to Cloud Run. It must not be interpreted as the cost of inference alone.

## 5. Interpretation and Limitations

1. The denominator is 17 scored predictions observed in six completed batches. It is a small sample and may not represent steady-state production usage.
2. These per-1,000 figures are provisional ratios. The billing export period and the log-derived prediction-count period have not yet been confirmed to align, so they must not be treated as validated unit costs.
3. Scheduled executions with no new files can consume resources without increasing the scored-prediction count.
4. The billing export selection covers 1–31 October 2026, but the report was prepared before the end of that period. Costs can change as the month progresses.
5. The CSV does not separately establish the amount of Free Trial credits applied or the final payable amount.
6. Artifact Registry network egress is a significant component of the current reported subtotal. It should be investigated separately from model inference and training costs.

## 6. Recommended Follow-up

- Re-export billing data after the reporting period or at a clearly recorded cutoff time.
- Align the billing cutoff with the Cloud Logging window used to count scored predictions.
- Track Cloud Run CPU and memory separately from image transfer, storage, and Vertex AI training.
- Recalculate cost per 1,000 scored predictions after collecting a larger number of batches.
- Record the export timestamp and the exact log-query window whenever this report is updated.

## 7. Data Sources

- Google Cloud Billing export CSV selected for 1–31 October 2026.
- Cloud Logging query for `resource.type="cloud_run_job"` and `resource.labels.job_name="lemon-batch"` over 1–31 October 2026 (UTC).
- Batch summary logs containing `batch_finished` events.
