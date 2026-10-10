# Evidence

Screenshots from the live deployment (project `lemon-mlops-project`, region `asia-southeast1`), taken
on 9 Oct 2026. Console times are Thailand time (UTC+7); times in the README are UTC.
`validator_audit.txt` is plain text output (`make validator-audit`).

| # | File | What it shows | Where it is used |
|---|---|---|---|
| 1 | `01-vertex-job-list.png` | Vertex AI custom job `lemon-train-train-20261008t140852z`: Finished, region, labels | README, "Data and training" |
| 2 | `02-vertex-job-detail.png` | The same job: `n1-standard-8`, 3 min 33 s, training image `lemon-train@sha256:fb541316…` | model manifest `training.image_digest` |
| 3 | `03-model-registry-version3.png` | Model Registry version 3 (`v2.1.0`): lineage JSON with git commit, data fingerprint, run id, serving digest, training image digest and job | README, "Model registry" |
| 4 | `04-mlflow-run-overview.png`, `04b-mlflow-model-metrics.png` | MLflow run `53c324d0…` of the cloud job: test accuracy 0.951, macro F1 0.9531, validation 0.9606 | `README_DATA_TRAINING.md` |
| 5 | `05-make-reproduce-pass.png` | `make reproduce` from a clean clone: same data fingerprint, 0.9510 vs claimed 0.951 ± 0.020, PASS | README, "Reproduce the model" |
| 6 | `06a-artifact-lemon-batch.png`, `06b-artifact-lemon-train.png` | Artifact Registry: images by digest. The deployed serving image is `73a09db082cf` (tag `c7fbd1d`); the training image is `fb541316…` | README, "The scheduled batch" |
| 7 | `07-cloud-run-executions.png` | Cloud Run job `lemon-batch`: executions starting every 30 minutes, all `1/1 completed` | README, cadence table |
| 8 | `08-cloud-scheduler.png` | Cloud Scheduler `lemon-batch-every-30min`: Enabled, `*/30 * * * *` (UTC), target is the `lemon-batch` job. "Last run" 16:02 was started by hand | README, cadence table |
| 9 | `09-ci-fail-tests.png` | CI on the deliberately broken commit `6b92682` (blur cutoff 0): 2 failed, 32 passed; `build` and publish did not run | README, "CI/CD" (CI blocks a bad commit) |
| 10 | `10-actions-batch-success.png` | Manual `batch.yml` run on the cloud-trained model (`v2.1.0`): 1 photo scored, summary JSON | README, "What the live deployment showed" |
| 11 | `11-dashboard-overview.png` | Cloud Monitoring dashboard overview | Monitoring evidence |
| 12 | `12-rejected-rate-alert.png` | Rejected-rate alert incident | Monitoring evidence |
| 13 | `13-low-confidence-alert.png` | Low-confidence alert incident | Monitoring evidence |
| 14 | `14-missed-run-alert-incident.png` | Missed-run alert incident screenshot | Monitoring evidence; pending team confirmation |
| 15 | `15-missed-run-metric-baseline.png` | Baseline for the missed-run monitoring metric | Monitoring evidence |
| 16 | `16-scheduler-resume-success.png` | Scheduler resume success in the console | Recovery evidence |
| 16b | `16b-scheduler-resume-success-wsl.png` | Scheduler resume success from WSL | Recovery evidence |

## Things a reader may wonder about

- **The MLflow run is named `v2.0.0`.** The cloud job ran before the version bump to `v2.1.0`, and the run name is taken from
  the version at the time. The model registry and the manifest record the model as `v2.1.0` with the same run id (`53c324d0…`).
- **The Model Registry list page still shows `v2.0.0` text.** That is the description of the model as first registered;
  each later version carries its own lineage in its version description (screenshot 3).
- **Two executions in screenshot 7 are manual** (16:02 from `make scheduler-run-now`, 16:10 from the console). Every other
  run was started by Cloud Scheduler.
- **Serving and training digests differ on purpose.** `fb541316…` is the image the model was trained in; `73a09db0…` is the image
  that serves it.
