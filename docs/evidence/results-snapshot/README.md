# Batch results snapshot (exported before teardown)

The 15 `results/batch-*.csv` files that were in the bucket on 17 October 2026, copied with
`gsutil -m cp "gs://lemon-mlops-project-data/lemon/results/*.csv" docs/evidence/results-snapshot/` (13.4 KiB in total).
Each file is one batch: one row per photo with status, predicted class, confidence, blur score, foliage ratio and
rejection reason (the columns of `CSV_COLUMNS` in `src/batch/run.py`). They contain file names and numbers only. The
latest batch is `batch-20261014T190027Z`; later runs found no new photos and wrote no results file.

Once the bucket is deleted, `make diagnose` can still be run on this copy:

```bash
make diagnose ARGS="--results-dir docs/evidence/results-snapshot --recent-batches 1"
```

It gives the output recorded in `../diagnose-cloud/README.md` (baseline 55 photos, 41 scored; recent 38 photos, 38 scored).
