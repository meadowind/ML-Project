"""The custom job runs the pinned training image as the project's service identity."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from cloudlayer.gcp import GcpAdapter

CFG = SimpleNamespace(
    provider="gcp", project_id="proj", region="asia-southeast1", blob_uri="blob://bucket/lemon",
    container_registry="reg/proj/lemon", model_registry_name="lemon-model",
    identity_ref="lemon-batch@proj.iam.gserviceaccount.com",
)
IMAGE = "reg/proj/lemon/lemon-train@sha256:" + "c" * 64


def test_spec_runs_the_image_on_one_cpu_machine_with_the_run_in_its_environment():
    spec = GcpAdapter(CFG)._training_spec(IMAGE, {"run_id": "train-1"})
    assert spec["replica_count"] == 1
    assert spec["machine_spec"]["machine_type"] == GcpAdapter.DEFAULT_TRAIN_MACHINE
    assert spec["container_spec"]["image_uri"] == IMAGE
    env = {e["name"]: e["value"] for e in spec["container_spec"]["env"]}
    assert env["TRAIN_IMAGE_REF"] == IMAGE and env["TRAIN_RUN_ID"] == "train-1"
    assert env["BLOB_URI"] == "blob://bucket/lemon" and env["CLOUD_PROVIDER"] == "gcp"
    assert all(isinstance(v, str) for v in env.values())


def test_machine_type_and_extra_environment_can_be_overridden():
    spec = GcpAdapter(CFG)._training_spec(
        IMAGE, {"run_id": "r", "machine_type": "n1-standard-16", "env": {"ALLOW_NEW_DATA": 1}})
    assert spec["machine_spec"]["machine_type"] == "n1-standard-16"
    env = {e["name"]: e["value"] for e in spec["container_spec"]["env"]}
    assert env["ALLOW_NEW_DATA"] == "1"


def test_an_image_tag_is_refused_so_the_training_is_reproducible():
    with pytest.raises(ValueError, match="digest-pinned"):
        GcpAdapter(CFG).submit_training("reg/proj/lemon/lemon-train:latest", {"run_id": "r"})
