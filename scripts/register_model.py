"""Register the production model in the cloud model registry, with lineage.

The registered version records: git commit, data hash, MLflow run, the digest-pinned
batch image that serves it, seed and metrics. Goes through the CloudAdapter only.

    python scripts/register_model.py --image <registry>/lemon-batch@sha256:...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FILES = ("model.torchscript.pt", "model_manifest.json")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_sha(manifest: dict) -> str | None:
    return (manifest.get("artifacts") or {}).get("torchscript_sha256")


def build_lineage(manifest: dict, image: str) -> dict[str, str]:
    """Flat str->str lineage. `image` must be digest-pinned so the version is reproducible."""
    if "@sha256:" not in image:
        raise ValueError("image must be digest-pinned (contain '@sha256:'); run `make image-push`")
    metrics = manifest.get("metrics", {}) or {}
    lin = manifest.get("dataset_lineage", {}) or {}
    hp = manifest.get("hyperparameters", {}) or {}
    raw = {
        "git_commit": manifest.get("git_commit"),
        "data_version": lin.get("processed_dir_sha256"),
        "dataset_revision": lin.get("revision_pinned"),
        "mlflow_run_id": manifest.get("mlflow_run_id"),
        "image_uri": image,
        "image_digest": image.split("@", 1)[1],
        "seed": hp.get("seed"),
        "model_version": manifest.get("version"),
        "torchscript_sha256": manifest_sha(manifest),
        "metric_val": metrics.get("best_val_accuracy"),
        "metric_test": metrics.get("test_accuracy"),
        "metric_macro_f1": metrics.get("macro_f1"),
    }
    return {k: str(v) for k, v in raw.items() if v is not None}


def register(adapter, model_dir: Path, image: str, registry_name: str) -> str:
    model_dir = Path(model_dir)
    for name in FILES:
        if not (model_dir / name).is_file():
            raise FileNotFoundError(f"{model_dir / name} missing - run `make train` first")
    manifest = json.loads((model_dir / "model_manifest.json").read_text(encoding="utf-8"))
    actual = sha256_file(model_dir / "model.torchscript.pt")
    expected = manifest_sha(manifest)
    if expected and expected != actual:
        raise ValueError("model.torchscript.pt does not match model_manifest.json (sha256 differs)")
    lineage = build_lineage(manifest, image)
    lineage["torchscript_sha256"] = actual
    prefix = f"models/{registry_name}/{actual[:12]}"
    for name in FILES:
        adapter.upload(str(model_dir / name), f"{prefix}/{name}")
    return adapter.register_model(adapter.uri_for(prefix), registry_name, lineage)


def main(argv: list[str] | None = None) -> int:
    from cloudlayer.factory import get_adapter
    from src import config

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--image", required=True, help="digest-pinned batch image reference")
    ap.add_argument("--model-dir", type=Path, default=Path("models/registry/lemon_classifier_v2"))
    args = ap.parse_args(argv)
    cfg = config.load()
    ref = register(get_adapter(cfg), args.model_dir, args.image, cfg.model_registry_name)
    print(f"registered: {ref}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
