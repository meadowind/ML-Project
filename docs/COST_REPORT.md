# MLOps Cost Report

## 1. Report Scope

- GCP project: `lemon-mlops-project`
- Region: `asia-southeast1`
- Cloud Run Job: `lemon-batch`
- Billing export period: 1–11 October 2026
- Billing export snapshot: 11 October 2026, 14:55 ICT
- Cloud Run executions covered by the reported execution count: 135
- Execution window: 8 October 2026, 13:30 UTC to 11 October 2026, 07:30 UTC
- Scored predictions in the same window (Cloud Logging): 17, in 6 batches
- Purpose: Summarize observed project costs and report the cost per 1,000 scored predictions, observed and marginal.
- Update: the schedule changed from every 30 minutes to every 2 hours on 12 October 2026; the effect is in Section 11.

The billing figures are from the export available at the snapshot time and may change as additional usage is recorded. The billing period (1–11 October) is longer than the execution and prediction window (8 October 13:30 UTC to 11 October 07:30 UTC). The Cloud Run charges are assumed to fall in that window because the job started running on 8 October; other items are shown for context. The billing export also lags, so ratios are indicative.

## 2. Batch Processing Summary

The supplied billing snapshot includes 135 Cloud Run executions for the period 8 October 2026, 13:30 UTC to 11 October 2026, 07:30 UTC.

For the same window, Cloud Logging shows 6 `batch_finished` events covering 21 files, of which 17 were scored (the rest were rejected). The other 129 executions found no new files and logged `batch_skipped`.

Scheduled executions can occur without new photos, so execution count and scored-prediction count are different measures of workload. The 17 scored predictions are the denominator used in section 6.

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

This is a list-price average of billed Cloud Run CPU and memory per execution. The Cloud Run free tier and Free Trial credits are not applied. At 48 scheduled runs per day (one every 30 minutes, the schedule used until 12 October 2026), the estimated cost is approximately THB 4.20 per day.

The billing export records 14,520 CPU-seconds at 2 vCPU. This corresponds to approximately 54 billed seconds per execution when divided by 135 executions and 2 vCPU. This is a billed average derived from aggregate usage, not a measured individual execution duration. Console-observed execution durations were approximately 12–40 seconds.

## 5. Fixed and Variable Cost View

### Execution-dependent costs

Cloud Run CPU and memory charges vary with billed resource usage. For the observed period, these charges totalled THB 11.71 across 135 executions, or approximately THB 0.087 per execution on average.

Until 12 October 2026 the job was scheduled every 30 minutes whether or not new photos were available (it now runs every 2 hours; see Section 11). Executions that find no new files can still contribute to operating costs without increasing the scored-prediction count.

### Recurring or capacity-related costs

Artifact Registry storage was THB 1.57 in the supplied export. Storage costs can recur while images remain stored, independent of how many predictions are scored during a particular execution.

### One-off or workload-specific costs

Artifact Registry internet egress was THB 5.35 for 1.33 GiB. The team reports that this usage came from GitHub Actions runners pulling the container image before the workflow moved to Cloud Scheduler. The recorded egress amount has remained unchanged since 9 October, and this transfer is understood to have stopped after the migration.

Vertex AI training-related charges totalled THB 1.13 for CPU, RAM, and SSD-backed persistent disk. These charges arose from training activity in the observed period and should not be treated as a recurring per-inference cost without further evidence.

This classification describes the observed usage and expected cost behavior; it does not imply that every charge is strictly fixed or that future usage will be identical.

## 6. Cost per 1,000 Scored Predictions

Window: 8 October 2026 13:30 UTC to 11 October 2026 07:30 UTC, the same window as the 135 Cloud Run executions. Predictions are counted from Cloud Logging (`jsonPayload.event="batch_finished"`, job `lemon-batch`): 6 batches, 21 files, 17 scored.

| Basis | THB | Per 1,000 scored predictions (THB) |
|---|---:|---:|
| Cloud Run CPU + memory (11.71 / 17) | 11.71 | 689 |
| All billed items in the export (19.77 / 17) | 19.77 | 1,163 |

These are observed, fully loaded figures. They are high because only 17 photos were scored in about three days, so scheduled runs that find nothing to do dominate the cost. They are not a per-photo price.

**Marginal cost.** Scoring one photo takes about one second on 2 vCPU / 2 GiB (an empty run takes about 12 s, a run with 10 photos about 21 s). At list price this is about THB 0.0016 per second, or about THB 1.6 per 1,000 photos. This is an estimate from run times, not a billed measurement.

**Sensitivity to volume.** The fixed run cost is about THB 4.20 per day (48 runs x THB 0.087). Spreading it over volume gives an estimated cost of about THB 43 per 1,000 predictions at 100 photos per day, THB 6 at 1,000 per day and THB 2 at 10,000 per day. These are estimates, not measurements.

The free tier and Free Trial credits are not applied. The THB 5.35 egress is a one-off cost and the Vertex AI charge is training-related, so the Cloud Run row is the better indicator of operating cost.

## 7. Interpretation and Limitations

1. The billing export covers 1–11 October 2026 at the snapshot taken on 11 October 2026, 14:55 ICT. The 135-execution count covers 8 October 2026, 13:30 UTC to 11 October 2026, 07:30 UTC; these periods are not fully aligned.
2. Cloud Run CPU and memory total THB 11.71 over 135 executions, approximately THB 0.087 per execution before applying the free tier or Free Trial credits.
3. The export records 14,520 vCPU-seconds over 135 executions at 2 vCPU, equivalent to approximately 54 billed seconds per execution. This is an aggregate billed-time average, not a measured individual runtime. Console-observed durations were approximately 12–40 seconds, and the gap is not fully explained.
4. At 48 scheduled runs per day (the original 30-minute schedule), Cloud Run CPU and memory cost is approximately THB 4.20 per day at list price, before free-tier usage or credits.
5. Cloud Run costs are largely run-related overhead. Runs that find no new photos can still incur cost without scoring photos. With 17 scored predictions in the window, the observed cost per 1,000 scored predictions is THB 689 (Cloud Run) and THB 1,163 (all billed items); the marginal cost is estimated at about THB 1.6 per 1,000 photos. The 17-prediction sample is small, so treat the observed figures as indicative.
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
- Recalculate cost per 1,000 scored predictions with a larger scored-prediction count and the billing cutoff recorded alongside the log window.
- Record the export timestamp and the exact log-query window whenever this report is updated.

## 10. Data Sources

- Google Cloud Billing export for 1–11 October 2026, snapshot taken 11 October 2026 at 14:55 ICT.
- Cloud Run execution count of 135 for the period 8 October 2026, 13:30 UTC to 11 October 2026, 07:30 UTC.
- Cloud Logging query for `resource.type="cloud_run_job"` and `resource.labels.job_name="lemon-batch"`.
- Batch summary logs containing `batch_finished` events.

## 11. Update: Effect of the Schedule Change (12–16 October 2026)

Sections 1–10 describe the 11 October 2026 snapshot and are kept as a dated record. Wherever they say the job runs every 30 minutes, that was the schedule until 12 October 2026. This section records the change and what the later billing exports show.

### 11.1 Change made

- On 12 October 2026 at 16:28 Thai time (09:28 UTC) the Cloud Scheduler entry `lemon-batch-every-30min` was changed from `*/30 * * * *` to `0 */2 * * *`, time zone `Asia/Bangkok`. The entry keeps its name because Cloud Scheduler jobs cannot be renamed.
- `lemon-batch-missed-run-alert` was changed from 1 hour to 4 hours without a successful execution.
- Reason: Section 2 found that 129 of 135 executions had no new files, and Section 4 puts the cost of an execution at about THB 0.087 whether or not it finds any.

### 11.2 Executions per day

Dates are UTC. Counted with `gcloud run jobs executions list --job lemon-batch --region=asia-southeast1 --format='value(metadata.creationTimestamp)' | cut -c1-10 | sort | uniq -c`.

| | 9 Oct | 10 Oct | 11 Oct | 12 Oct | 13 Oct | 14 Oct | 15 Oct |
|---|---:|---:|---:|---:|---:|---:|---:|
| Executions | 47 | 46 | 52 | 26 | 12 | 12 | 12 |
| Schedule | 30 min | 30 min | 30 min, a few manual runs | changed mid-day | 2 h | 2 h | 2 h |

16 October had 5 executions at the time of the check (01:00 to 09:00 UTC), as scheduled. Twelve executions a day match `0 */2 * * *`, so nothing else is starting the job.

### 11.3 Billing exports compared

The exports are cumulative for 1–31 October 2026, in THB at list price, with no daily breakdown.

| Export | Cloud Run CPU-seconds | Cloud Run CPU + memory | Artifact Registry storage | Egress, Vertex AI, other | Total |
|---|---:|---:|---:|---:|---:|
| 11 October, 14:55 ICT (Section 3) | 14,520 | 11.71 | 1.57 | 6.49 | 19.77 |
| 13 October (time not recorded) | 23,640 | 19.06 | 3.99 | 6.49 | 29.54 |
| 15 October, 18:01 ICT | 26,640 | 21.48 | 6.80 | 6.49 | 34.77 |

Egress and Vertex AI did not change between exports, as Section 5 expected. The total keeps rising because the exports are cumulative, not because the new schedule costs more.

### 11.4 Cloud Run cost per execution and per day

Between the 13 and 15 October exports, Cloud Run CPU and memory rose by THB 2.42 and billed CPU-seconds by 3,000, which is about 1,500 billed seconds at 2 vCPU. That interval is about two days and holds roughly 22 to 27 executions (the 13 October export time was not recorded, so the count is approximate).

| | Every 30 minutes (until 12 October) | Every 2 hours (from 12 October) |
|---|---:|---:|
| Executions per day | about 48 | 12 |
| Cloud Run CPU + memory per execution | about THB 0.087 | about THB 0.09–0.11 |
| Cloud Run CPU + memory per day | about THB 4.2–4.3 | about THB 1.3 |

This is roughly 70% lower. The cost per execution did not change within the uncertainty, so the saving comes from running less often. Cross-check: 12 executions x THB 0.09–0.11 is THB 1.1–1.3 a day.

### 11.5 Cost per 1,000 predictions at the new schedule (estimate)

The observed figures in Section 6 (THB 689 and THB 1,163) are not recomputed, because that needs a scored-prediction count over a window aligned with the billing cutoff. Using the Section 6 method with the fixed cost of about THB 1.3 a day and the marginal THB 1.6 per 1,000 photos:

| Photos per day | Every 30 minutes (Section 6) | Every 2 hours |
|---:|---:|---:|
| 100 | about THB 43 | about THB 15 |
| 1,000 | about THB 6 | about THB 3 |
| 10,000 | about THB 2 | about THB 2 |

These are estimates, not measurements.

### 11.6 Artifact Registry storage is now larger than Cloud Run per day

Storage rose from THB 3.99 to THB 6.80 between the last two exports (1.30 to 2.14 GiB-months), about THB 1.5 a day, which is more than the Cloud Run cost above. At about THB 3.1 per GiB-month in the export, that implies on the order of 10–15 GiB stored on average. This is inferred from the price, not a measured repository size. The likely cause is that CI publishes an image on every commit to `main` and nothing is deleted, but the repository contents have not been inspected (the account used for these checks could not list repositories). No cleanup policy has been set.

### 11.7 Trade-offs

- A photo can wait up to about 2 hours plus run time (previously 30 minutes).
- A failed run is flagged after about 4 hours (previously 1 hour). If the missed-run alert gives false alarms, raise the window to 5 hours.

### 11.8 Comparing before and after fairly

- Use full days on one schedule only: 9–10 October before, 13–15 October after. Skip 11 October (manual runs) and 12 October (changed mid-day).
- In Billing, Reports, pull one day at a time, Cloud Run only (CPU and memory). Check the report's time zone, because its day boundaries may not match Thai time.
- Compare THB per day, THB per execution and photos scored per day. Exclude days with demo or test uploads, since runs that find photos take longer.

### 11.9 Limitations

- Exports are cumulative, and the 13 October export time was not recorded (Section 9 asked for this). Per-day figures are differences between exports, so allow about 10% either way.
- Billing usage lags, and the free tier and Free Trial credits are not applied.
- The implied stored size in 11.6 is an inference.

### 11.10 Follow-up

- Re-export billing by day after three full days on the new schedule and replace the estimates in 11.4 and 11.5.
- Set an Artifact Registry cleanup policy in dry-run mode first. Keep the digest used by the Cloud Run job, the image registered in Vertex AI Model Registry, the training image digest in the lineage, and digests cited in `docs/evidence/`.
- Not done: upload-triggered runs (needs a lock against overlapping executions and a new missed-run alert), right-sizing from 2 vCPU / 2 GiB to 1 vCPU / 1 GiB, and shortening the roughly 10 s start-up of an empty run.
