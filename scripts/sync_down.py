"""Pull NEW intake images from object storage into data/intake/.

"New" = not already present under archive/ or quarantine/ (remote or local). The CI runner
starts empty, so the remote prefixes are the source of truth for what was processed.
Provider-neutral: goes through the CloudAdapter only.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cloudlayer.factory import get_adapter
from src import config
from src.batch.run import IMAGE_SUFFIXES


def names(keys: list[str]) -> set[str]:
    return {PurePosixPath(k).name for k in keys}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--reprocess", action="store_true", help="download everything in intake/")
    args = ap.parse_args(argv)

    cfg = config.load(strict=False)
    adapter = get_adapter(cfg)
    data = args.data_dir or Path(cfg.data_dir)

    done: set[str] = set()
    if not args.reprocess:
        done |= names(adapter.list_keys("archive/")) | names(adapter.list_keys("quarantine/"))
        for sub in ("archive", "quarantine"):
            d = data / sub
            if d.is_dir():
                done |= {p.name for p in d.iterdir() if p.is_file()}

    fetched = skipped = 0
    for key in adapter.list_keys("intake/"):
        name = PurePosixPath(key).name
        if PurePosixPath(name).suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if name in done:
            skipped += 1
            continue
        adapter.download(adapter.uri_for(key), str(data / "intake" / name))
        fetched += 1
    (data / "intake").mkdir(parents=True, exist_ok=True)
    print(f"sync_down: fetched={fetched} already_processed={skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
