"""Where a model was trained: recorded in the manifest, the MLflow run and the registry lineage.

Torch-free on purpose, so tests and the batch image can import it. Everything comes from
environment variables set by whoever launched the training (see scripts/train_cloud.py).
"""
from __future__ import annotations

import os
from collections.abc import Mapping


def git_commit_from_env(env: Mapping[str, str] | None = None) -> str | None:
    """Commit baked into a container image at build time (there is no .git inside it)."""
    value = (os.environ if env is None else env).get("GIT_COMMIT", "")
    return value if value and value != "unknown" else None


def training_info(env: Mapping[str, str] | None = None) -> dict[str, str]:
    """`{"environment": "local"}` on a laptop; image digest, run id and job id in a cloud job."""
    env = os.environ if env is None else env
    image = env.get("TRAIN_IMAGE_REF", "")
    if not image:
        return {"environment": "local"}
    run_id = env.get("TRAIN_RUN_ID", "")
    info = {
        "environment": "cloud-job",
        "image_ref": image,
        "image_digest": image.split("@", 1)[1] if "@sha256:" in image else "",
        "run_id": run_id,
        "job": env.get("CLOUD_ML_JOB_ID") or run_id,
    }
    return {k: v for k, v in info.items() if v}
