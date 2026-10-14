"""Write SIMULATED batch result files so `make diagnose` can be shown on a clear drift.

The real bucket holds too few scored photos for the drift tests (30 per window), and a quality drop
cannot be produced on demand. This writes results/*.csv in the same format as the real batch, with
a stable baseline followed by recent batches that go wrong in one chosen way. Nothing here is real
data and nothing touches the cloud: every row is marked with model_version "SIMULATED".

    python scripts/simulate_drift_demo.py --scenario bad_uploads --out demo_sim/bad_uploads
    python scripts/diagnose_performance.py --results-dir demo_sim/bad_uploads/results
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.batch.run import CSV_COLUMNS

SCENARIOS = {
    "stable": "Nothing changes: diagnose should report no evidence of drift.",
    "bad_uploads": "Many blurred photos start arriving: image quality problem (rejections).",
    "non_leaf": "Photos that are not lemon leaves start arriving: out-of-domain inputs.",
    "model_uncertainty": "Same kind of photos, but the model is less confident: model problem.",
    "covariate_drift": "Photos look different (blurrier, less foliage) and confidence falls.",
}
CLASSES = ["Healthy_Leaf", "Citrus_Canker", "Dry_Leaf"]
CLASS_WEIGHTS = [0.55, 0.25, 0.20]
BASELINE_BATCHES, RECENT_BATCHES, PHOTOS = 6, 3, 25   # 150 baseline / 75 recent photos


def photo(rng: random.Random, batch: str, i: int, when: str, *, conf: float, blur: float,
          foliage: float, status: str = "SCORED") -> dict:
    scored = status == "SCORED"
    cls = rng.choices(CLASSES, CLASS_WEIGHTS)[0] if scored else ""
    confidence = min(max(rng.gauss(conf, 0.06), 0.30), 0.999) if scored else None
    return {
        "batch_id": batch, "filename": f"sim-{batch[-8:]}-{i:02d}.jpg", "status": status,
        "predicted_class": cls, "confidence": f"{confidence:.3f}" if scored else "",
        "needs_inspection": str(bool(scored and (cls != CLASSES[0] or confidence < 0.60))).lower(),
        "model_version": "SIMULATED", "blur_score": f"{max(rng.gauss(blur, 25), 5):.1f}",
        "foliage_ratio": f"{min(max(rng.gauss(foliage, 0.05), 0.02), 0.95):.3f}",
        "rejection_reason": status.removeprefix("REJECTED_").lower() if not scored else "",
        "processed_at": when,
    }


def build(scenario: str, seed: int = 355) -> list[dict]:
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}; choose from {', '.join(SCENARIOS)}")
    rng = random.Random(seed)
    rows: list[dict] = []
    total = BASELINE_BATCHES + RECENT_BATCHES
    for b in range(total):
        recent = b >= BASELINE_BATCHES and scenario != "stable"
        day, hour = 1 + b // 12, (b % 12) * 2
        batch = f"batch-202610{day:02d}T{hour:02d}0000Z"
        when = f"2026-10-{day:02d}T{hour:02d}:00:00Z"
        conf, blur, foliage = 0.92, 160.0, 0.45
        bad_status, bad_share = "", 0.0
        if recent and scenario == "bad_uploads":
            bad_status, bad_share = "REJECTED_BLURRED", 0.40
        elif recent and scenario == "non_leaf":
            bad_status, bad_share = "REJECTED_OOD_NON_LEAF", 0.35
        elif recent and scenario == "model_uncertainty":
            conf = 0.52
        elif recent and scenario == "covariate_drift":
            conf, blur, foliage = 0.60, 70.0, 0.22
        for i in range(PHOTOS):
            status = bad_status if bad_status and rng.random() < bad_share else "SCORED"
            rows.append(photo(rng, batch, i, when, conf=conf, blur=blur, foliage=foliage, status=status))
    return rows


def write(rows: list[dict], out: Path) -> list[Path]:
    results = out / "results"
    results.mkdir(parents=True, exist_ok=True)
    paths = []
    for batch in sorted({r["batch_id"] for r in rows}):
        path = results / f"{batch}.csv"
        with path.open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(r for r in rows if r["batch_id"] == batch)
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--scenario", choices=sorted(SCENARIOS), default="bad_uploads")
    ap.add_argument("--out", type=Path, default=ROOT / "demo_sim")
    ap.add_argument("--seed", type=int, default=355)
    args = ap.parse_args(argv)
    paths = write(build(args.scenario, args.seed), args.out)
    print(f"SIMULATED data ({args.scenario}): {SCENARIOS[args.scenario]}")
    print(f"wrote {len(paths)} files to {args.out / 'results'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
