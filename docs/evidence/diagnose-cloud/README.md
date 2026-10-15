# `make diagnose` on real batches in the bucket

Command, run on 15 Oct 2026 (Asia/Bangkok) after the batch of 14 Oct 19:00 UTC:

```
make diagnose ARGS="--from-cloud --recent-batches 1"
```

Screenshot: `26-diagnose-from-cloud-batch-20261014.png`. The output was:

```
Recent window: 1 batch(es) batch-20261014T190027Z
Baseline: 55 photos (41 scored); recent: 38 photos (38 scored)

| Signal | Baseline | Recent | Flag | Detail |
|---|---:|---:|:--:|---|
| rejected rate | 25.5% | 0.0% | ok |  |
| low-confidence rate | 19.5% | 0.0% | ok | threshold 0.60 |
| mean confidence | 0.908 | 0.993 | ok |  |
| confidence distribution (PSI) | - | 1.800 | FLAG | major |
| predicted-class mix (PSI) | - | 1.942 | FLAG | major |
| blur score (KS) | 587.916 | 855.128 | FLAG | D=0.294, critical 0.292; baseline/recent show medians |
| foliage ratio (KS) | 0.424 | 0.392 | ok | D=0.241, critical 0.302; baseline/recent show medians |
```

## How to read it

- **This is real data in the bucket, but the recent batch is not natural traffic.** The team uploaded a hand-picked set of
  demo photos (renamed copies) to get at least 30 scored photos in one batch, which is the minimum for the distribution
  tests. The set is easier and less varied than the earlier photos, so the model is more confident and the mix of predicted
  diseases changed. `make diagnose` flagged that the batch differs from earlier ones, which is what it is for.
- **No alert would have fired.** The batch had no rejected photos and none below the 0.60 confidence threshold, so the rejected-rate
  and low-confidence alerts stayed quiet. The distribution tests still saw the change.
- **The blur flag is marginal** (D 0.294 against a critical value of 0.292) and rests on 38 photos. Treat it as a hint.
- **This is not evidence of real-world drift and says nothing about accuracy.** Production photos have no labels, so accuracy is
  not measured; the "covariate drift" cause is a lead for a person to check, and here the explanation is how we chose the photos.
- For clear, labelled examples of each cause, see `../diagnose-simulated/` (simulated data).
