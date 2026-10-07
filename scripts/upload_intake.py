"""Demo helper: put local images into intake/ in object storage (simulates a user upload)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: python scripts/upload_intake.py <image> [<image> ...]", file=sys.stderr)
        return 2
    adapter = get_adapter(config.load(strict=False))
    for arg in argv:
        path = Path(arg)
        print(adapter.upload(str(path), f"intake/{path.name}"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
