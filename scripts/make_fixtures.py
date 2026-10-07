"""Generate small deterministic test images (no dataset needed, nothing downloaded).

    python scripts/make_fixtures.py [out_dir]     # default: tests/fixtures (gitignored)

good_leaf.jpg    green, sharp texture   -> should pass the validator
blurred_leaf.jpg same, heavily blurred  -> REJECTED_BLURRED
not_a_leaf.jpg   blue/grey, textured    -> REJECTED_OOD_NON_LEAF
tiny.jpg         16x16                  -> REJECTED_RESOLUTION
corrupt.jpg      random bytes           -> REJECTED_CORRUPTED
empty.jpg        0 bytes                -> REJECTED_CORRUPTED
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def _textured(rgb: tuple[int, int, int], size: int, seed: int) -> Image.Image:
    rng = np.random.default_rng(seed)
    base = np.zeros((size, size, 3), dtype=np.float32) + np.array(rgb, dtype=np.float32)
    noise = rng.normal(0, 28, (size, size, 1)).astype(np.float32)
    # veins: sharp diagonal lines give the Laplacian something to measure
    yy, xx = np.mgrid[0:size, 0:size]
    veins = (((xx + yy) % 24) < 3).astype(np.float32)[..., None] * 40
    return Image.fromarray(np.clip(base + noise + veins, 0, 255).astype(np.uint8))


def make(out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = {name: out / name for name in (
        "good_leaf.jpg", "blurred_leaf.jpg", "not_a_leaf.jpg", "tiny.jpg", "corrupt.jpg", "empty.jpg")}
    leaf = _textured((50, 140, 40), 384, seed=1)
    leaf.save(paths["good_leaf.jpg"], quality=95)
    leaf.filter(ImageFilter.GaussianBlur(14)).save(paths["blurred_leaf.jpg"], quality=95)
    _textured((70, 90, 180), 384, seed=2).save(paths["not_a_leaf.jpg"], quality=95)
    _textured((50, 140, 40), 16, seed=3).save(paths["tiny.jpg"], quality=95)
    paths["corrupt.jpg"].write_bytes(b"\xff\xd8\xff\xe0 this is not really a jpeg" + bytes(range(200)))
    paths["empty.jpg"].write_bytes(b"")
    return paths


if __name__ == "__main__":
    default = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else default
    for name, p in make(target).items():
        print(f"{name:<18} {p.stat().st_size:>8} bytes")
