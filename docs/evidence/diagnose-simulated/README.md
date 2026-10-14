# Simulated drift scenarios for `make diagnose`

**Everything in this folder is simulated. None of it is real production data.**

The deployed project has scored fewer than 30 photos, which is too few for `make diagnose` to run its drift tests, and a
quality drop cannot be produced on demand. `scripts/simulate_drift_demo.py` therefore writes result files in the same
format as the real batch (`model_version` is `SIMULATED`), with six stable batches followed by three batches that go wrong
in one chosen way. Nothing touches the cloud and nothing is trained or scored.

| File | What was simulated | What `make diagnose` concluded |
| --- | --- | --- |
| `stable.md` | No change | No evidence of drift |
| `bad_uploads.md` | 40% of recent photos are blurred | Image quality: more blurred photos |
| `non_leaf.md` | 35% of recent photos are not leaves | Out-of-domain inputs |
| `model_uncertainty.md` | Same photos, lower confidence | Model uncertainty, possible concept drift |
| `covariate_drift.md` | Blurrier, less foliage, lower confidence | Covariate drift |

This shows the diagnosis logic reaches the right conclusion when the signals move. It does not show how often real
drift happens or that the thresholds are tuned for real photos. Reproduce any row with `make diagnose-demo SCENARIO=<name>`
(output goes to the git-ignored `demo_sim/`).
