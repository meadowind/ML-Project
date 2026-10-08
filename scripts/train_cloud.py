"""Run training on cloud compute: push the training image, start the job, wait for it.

    make train-cloud                      # builds lemon-train:<sha>, pushes, trains, waits
    python scripts/train_cloud.py --image lemon-train:abc1234 --run-id train-demo

The job rebuilds the dataset, checks its fingerprint against data/dataset_lineage.json, trains
with the pinned dependencies and publishes the model under models/trained/<run id>/ in the
project storage. Fetch it with `make fetch-trained RUN=<run id>`. Goes through the
CloudAdapter only.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def new_run_id() -> str:
    return "train-" + datetime.now(timezone.utc).strftime("%Y%m%dt%H%M%Sz").lower()


def main(argv: list[str] | None = None) -> int:
    from cloudlayer.factory import get_adapter
    from src import config

    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--image", help="locally built training image, e.g. lemon-train:abc1234")
    ap.add_argument("--wait", metavar="JOB", help="only wait for this already-submitted job (resource name)")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--machine-type", default=None)
    ap.add_argument("--no-wait", action="store_true", help="submit and return immediately")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    adapter = get_adapter(config.load())
    if args.wait:
        print(adapter.wait_training(args.wait), flush=True)
        return 0
    if not args.image:
        ap.error("--image is required unless --wait is given")
    run_id = args.run_id or new_run_id()
    image_ref = adapter.push_image(args.image)
    print(f"training image: {image_ref}", flush=True)
    job = adapter.submit_training(image_ref, {"run_id": run_id, "machine_type": args.machine_type})
    print(f"submitted: {job}\nrun id: {run_id}", flush=True)
    if args.no_wait:
        return 0
    print(adapter.wait_training(job), flush=True)
    print(f"model files: {adapter.uri_for(f'models/trained/{run_id}/')}")
    print(f"next: make fetch-trained RUN={run_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
