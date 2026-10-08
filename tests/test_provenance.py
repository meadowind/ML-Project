"""Where a model was trained is recorded, and survives into the registry lineage."""
from __future__ import annotations

from register_model import build_lineage

from src.model.provenance import git_commit_from_env, training_info

DIGEST = "sha256:" + "b" * 64
TRAIN_IMAGE = f"reg/lemon-train@{DIGEST}"
SERVE_IMAGE = "reg/lemon-batch@sha256:" + "a" * 64


def test_laptop_run_says_local():
    assert training_info({}) == {"environment": "local"}


def test_cloud_run_records_image_digest_run_and_job():
    info = training_info({"TRAIN_IMAGE_REF": TRAIN_IMAGE, "TRAIN_RUN_ID": "train-1",
                          "CLOUD_ML_JOB_ID": "12345"})
    assert info == {"environment": "cloud-job", "image_ref": TRAIN_IMAGE, "image_digest": DIGEST,
                    "run_id": "train-1", "job": "12345"}


def test_job_falls_back_to_run_id_when_the_platform_gives_no_job_id():
    info = training_info({"TRAIN_IMAGE_REF": TRAIN_IMAGE, "TRAIN_RUN_ID": "train-1"})
    assert info["job"] == "train-1"


def test_commit_comes_from_the_image_when_there_is_no_git():
    assert git_commit_from_env({"GIT_COMMIT": "abc123"}) == "abc123"
    assert git_commit_from_env({"GIT_COMMIT": "unknown"}) is None
    assert git_commit_from_env({}) is None


def test_lineage_carries_the_training_environment():
    manifest = {"training": training_info({"TRAIN_IMAGE_REF": TRAIN_IMAGE, "TRAIN_RUN_ID": "train-1"})}
    lineage = build_lineage(manifest, SERVE_IMAGE)
    assert lineage["training_image_digest"] == DIGEST
    assert lineage["training_environment"] == "cloud-job" and lineage["training_job"] == "train-1"


def test_lineage_of_a_laptop_model_has_no_training_image():
    lineage = build_lineage({"training": {"environment": "local"}}, SERVE_IMAGE)
    assert lineage["training_environment"] == "local"
    assert "training_image_digest" not in lineage
    assert "training_environment" not in build_lineage({}, SERVE_IMAGE)  # models trained before this field
