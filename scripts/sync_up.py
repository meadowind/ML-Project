"""Push batch outputs (archive, quarantine, results, summary, logs) to object storage.

intake/ is never modified or deleted — it is the immutable input, which is what makes a
batch replayable. Provider-neutral: goes through the CloudAdapter only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter

from src import config

# local subfolder (relative to data dir) -> remote prefix
MAPPING = {
    "archive": "archive",
    "quarantine": "quarantine",
    "output/results": "results",
    "output/summary": "summary",
    "output/logs": "logs",
}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    cfg = config.load(strict=False)
    adapter = get_adapter(cfg)
    data = args.data_dir or Path(cfg.data_dir)

    sent = 0
    for local, remote in MAPPING.items():
        folder = data / local
        if not folder.is_dir():
            continue
        for path in sorted(p for p in folder.iterdir() if p.is_file()):
            adapter.upload(str(path), f"{remote}/{path.name}")
            sent += 1
    print(f"sync_up: uploaded={sent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
