"""Training job entry point: runs inside the training container (a cloud custom job).

    python scripts/train_job.py

1. rebuilds the dataset from the pinned upstream revision and checks its fingerprint against
   the committed data/dataset_lineage.json, so "same data" is verified, not assumed;
2. trains (src/model/train.py), tracking the run in MLflow;
3. publishes the model files and the MLflow database under models/trained/<run id>/ in the
   project storage, through the CloudAdapter (the identity attached to the job; no keys).

Environment: TRAIN_RUN_ID (default train-<UTC time>), ALLOW_NEW_DATA=1 to accept a different
dataset fingerprint. This script imports no ML libraries; the heavy work is in subprocesses.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
LINEAGE = ROOT / "data" / "dataset_lineage.json"
OUT_DIR = Path("/tmp/out/lemon_classifier")  # container scratch space
MLFLOW_DB = Path("/tmp/mlflow.db")
MODEL_FILES = ("model.torchscript.pt", "weights.pt", "model_manifest.json")
PREFIX = "models/trained"


def fingerprint(lineage_path: Path = LINEAGE) -> str:
    return json.loads(lineage_path.read_text(encoding="utf-8"))["processed_dir_sha256"]


def ensure_same_data(expected: str, actual: str, allow_new: bool = False) -> None:
    if expected == actual:
        return
    message = f"dataset fingerprint changed: expected {expected}, got {actual}"
    if not allow_new:
        raise RuntimeError(message + " (set ALLOW_NEW_DATA=1 to accept a different dataset)")
    print(json.dumps({"event": "data_changed", "detail": message}), flush=True)


def publish(adapter, out_dir: Path, run_id: str, extra: tuple[Path, ...] = ()) -> str:
    """Upload the trained files; returns the storage URI of the run's folder."""
    sent = 0
    for path in [out_dir / name for name in MODEL_FILES] + list(extra):
        if path.is_file():
            adapter.upload(str(path), f"{PREFIX}/{run_id}/{path.name}")
            sent += 1
    if not (out_dir / "model.torchscript.pt").is_file():
        raise FileNotFoundError("training finished without model.torchscript.pt")
    print(json.dumps({"event": "model_published", "files": sent,
                      "uri": adapter.uri_for(f"{PREFIX}/{run_id}/")}), flush=True)
    return adapter.uri_for(f"{PREFIX}/{run_id}/")


def run(cmd: list[str], **env: str) -> None:
    print(json.dumps({"event": "step", "cmd": " ".join(cmd)}), flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT, env={**os.environ, **env})


def main() -> int:
    from cloudlayer.factory import get_adapter
    from src import config

    run_id = os.environ.get("TRAIN_RUN_ID") or "train-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.environ["TRAIN_RUN_ID"] = run_id
    expected = fingerprint()
    run([sys.executable, "src/data/download_and_prep.py"])
    ensure_same_data(expected, fingerprint(), os.environ.get("ALLOW_NEW_DATA") == "1")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    run([sys.executable, "src/model/train.py"], MODEL_OUT_DIR=str(OUT_DIR), TRAIN_RUN_ID=run_id)
    publish(get_adapter(config.load(strict=False)), OUT_DIR, run_id, extra=(MLFLOW_DB,))
    return 0


if __name__ == "__main__":
    sys.exit(main())
