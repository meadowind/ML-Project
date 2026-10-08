"""Bring a cloud-trained model home, verify it, and compare it with the committed one.

    make fetch-trained RUN=train-20261009t...            # download + verify + compare
    make fetch-trained RUN=train-... ARGS=--adopt        # also copy into models/registry/...

Files land in reports/trained/<run>/ (never over the committed model) unless --adopt is given.
Goes through the CloudAdapter only.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from register_model import sha256_file

PREFIX = "models/trained"
FILES = ("model.torchscript.pt", "model_manifest.json")
METRICS = ("best_val_accuracy", "test_accuracy", "macro_f1", "clean_test_low_confidence_pct")


def verify(folder: Path, committed_data_hash: str | None) -> dict:
    """Return the manifest after checking the weights hash and, if known, the dataset hash."""
    manifest = json.loads((folder / "model_manifest.json").read_text(encoding="utf-8"))
    expected = (manifest.get("artifacts") or {}).get("torchscript_sha256")
    actual = sha256_file(folder / "model.torchscript.pt")
    if expected != actual:
        raise ValueError(f"model.torchscript.pt hash {actual} does not match the manifest ({expected})")
    data_hash = (manifest.get("dataset_lineage") or {}).get("processed_dir_sha256")
    if committed_data_hash and data_hash != committed_data_hash:
        raise ValueError(f"trained on different data: {data_hash} (committed: {committed_data_hash})")
    return manifest


def compare(new: dict, old: dict) -> list[str]:
    rows = [f"{'':32}{'committed':>12}{'cloud run':>12}"]
    for key in METRICS:
        a = (old.get("metrics") or {}).get(key)
        b = (new.get("metrics") or {}).get(key)
        rows.append(f"{key:32}{a if a is not None else '-':>12}{b if b is not None else '-':>12}")
    for label, getter in (
        ("torch", lambda m: (m.get("framework_versions") or {}).get("torch")),
        ("trained in", lambda m: (m.get("training") or {}).get("environment")),
        ("git commit", lambda m: str(m.get("git_commit", ""))[:10]),
    ):
        rows.append(f"{label:32}{getter(old) or '-'!s:>12}{getter(new) or '-'!s:>12}")
    return rows


def main(argv: list[str] | None = None) -> int:
    from cloudlayer.factory import get_adapter
    from src import config

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--committed", type=Path, default=Path("models/registry/lemon_classifier_v2"))
    ap.add_argument("--adopt", action="store_true", help="copy the verified files over --committed")
    args = ap.parse_args(argv)

    adapter = get_adapter(config.load(strict=False))
    out = args.out or Path("reports/trained") / args.run
    for name in FILES:
        adapter.download(adapter.uri_for(f"{PREFIX}/{args.run}/{name}"), str(out / name))

    old_path = args.committed / "model_manifest.json"
    old = json.loads(old_path.read_text(encoding="utf-8")) if old_path.is_file() else {}
    manifest = verify(out, (old.get("dataset_lineage") or {}).get("processed_dir_sha256"))
    print("\n".join(compare(manifest, old)))
    print(f"\nverified: weights hash and dataset hash match. Files in {out}")
    if args.adopt:
        for name in FILES:
            shutil.copy2(out / name, args.committed / name)
        print(f"adopted into {args.committed}: review `git diff`, run the tests, open a PR")
    return 0


if __name__ == "__main__":
    sys.exit(main())
