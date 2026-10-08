"""One scheduled cycle inside the container: pull new photos, score them, push results.

    python scripts/cloud_batch.py                # what Cloud Run executes every 30 minutes
    python scripts/cloud_batch.py --reprocess    # replay everything in intake/

Same three steps as `make run-batch` (sync_down -> src.batch.run -> sync_up), in one
process, so the job needs nothing from the machine that starts it. Storage access goes
through the CloudAdapter with whatever identity the host attaches (on Cloud Run, the job's
service account), so there is no key file anywhere. Working files live under DATA_DIR
(default /tmp/data) and vanish with the container; the bucket is the only state.

Exit code is non-zero when any step fails, which is what marks the execution as failed.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import sync_down
import sync_up

from src.batch import run

DEFAULT_DATA_DIR = "/tmp/data"  # container scratch space; the bucket is the only state


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--reprocess", action="store_true",
                    help="ignore archive/quarantine and score everything in intake/ again")
    args = ap.parse_args(argv)

    data = Path(os.environ.setdefault("DATA_DIR", DEFAULT_DATA_DIR))
    extra = ["--reprocess"] if args.reprocess else []

    steps = (
        ("sync_down", lambda: sync_down.main(["--data-dir", str(data), *extra])),
        ("score", lambda: run.main(extra)),
        ("sync_up", lambda: sync_up.main(["--data-dir", str(data)])),
    )
    for name, step in steps:
        code = step()
        if code:
            print(f"cloud_batch: step {name} failed with exit code {code}", file=sys.stderr, flush=True)
            return code
    return 0


if __name__ == "__main__":
    sys.exit(main())
