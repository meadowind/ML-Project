"""Prove the registered model is usable: pull it back BY VERSION from the registry and score
held-out images. Exits non-zero if the pulled model is corrupt or gives invalid output.

    python scripts/reload_check.py [--ref lemon-leaf-classifier@3] [--images data/processed/test]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from register_model import manifest_sha, sha256_file

SUFFIXES = {".jpg", ".jpeg", ".png"}


def pick_images(root: Path, n: int) -> list[Path]:
    """Spread picks across class folders so one class cannot hide a broken model."""
    folders = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    pools = [sorted(f for f in d.iterdir() if f.suffix.lower() in SUFFIXES) for d in folders] or [
        sorted(f for f in root.iterdir() if f.suffix.lower() in SUFFIXES)
    ]
    out: list[Path] = []
    i = 0
    while len(out) < n and any(i < len(p) for p in pools):
        out += [p[i] for p in pools if i < len(p)][: n - len(out)]
        i += 1
    return out


def verify_files(local: Path) -> dict:
    import json

    manifest = json.loads((local / "model_manifest.json").read_text(encoding="utf-8"))
    expected = manifest_sha(manifest)
    if expected and sha256_file(local / "model.torchscript.pt") != expected:
        raise ValueError("pulled model does not match its manifest sha256")
    return manifest


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ref", default=None, help="name or name@version (default: registry name, latest)")
    ap.add_argument("--images", type=Path, default=Path("data/processed/test"))
    ap.add_argument("-n", type=int, default=5)
    args = ap.parse_args(argv)

    from PIL import Image

    from cloudlayer.factory import get_adapter
    from src import config
    from src.model.inference import load_model, predict

    cfg = config.load()
    adapter = get_adapter(cfg)
    ref = args.ref or cfg.model_registry_name
    with tempfile.TemporaryDirectory() as tmp:
        lineage = adapter.fetch_model(ref, tmp)
        verify_files(Path(tmp))
        model, classes, _ = load_model(Path(tmp))
        print(f"pulled {lineage.get('resolved_ref', ref)}  git={lineage.get('git_commit')}  "
              f"data={str(lineage.get('data_version'))[:12]}  image={lineage.get('image_digest', '')[:19]}")
        files = pick_images(args.images, args.n)
        if not files:
            print(f"FAIL: no images under {args.images}")
            return 1
        bad = 0
        for f in files:
            label, conf = predict(Image.open(f), model, classes)
            ok = label in classes and 0.0 <= conf <= 1.0
            bad += not ok
            print(f"  {f.parent.name}/{f.name}: {label} ({conf:.3f}) {'ok' if ok else 'INVALID'}")
    print("reload_check: PASSED" if not bad else f"reload_check: FAILED ({bad} invalid)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
