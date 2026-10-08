"""A fetched model is accepted only if its weights and data match what the manifest claims."""
from __future__ import annotations

import json

import pytest
from fetch_trained import compare, verify
from register_model import sha256_file


def _folder(tmp_path, data_hash="d" * 64, tamper=False):
    folder = tmp_path / "run"
    folder.mkdir()
    (folder / "model.torchscript.pt").write_bytes(b"weights")
    claimed = "0" * 64 if tamper else sha256_file(folder / "model.torchscript.pt")
    manifest = {"artifacts": {"torchscript_sha256": claimed},
                "dataset_lineage": {"processed_dir_sha256": data_hash},
                "metrics": {"test_accuracy": 0.96}, "framework_versions": {"torch": "2.6.0+cpu"},
                "training": {"environment": "cloud-job"}, "git_commit": "abcdef0123456789"}
    (folder / "model_manifest.json").write_text(json.dumps(manifest))
    return folder


def test_matching_files_are_accepted(tmp_path):
    assert verify(_folder(tmp_path), "d" * 64)["metrics"]["test_accuracy"] == 0.96


def test_a_tampered_model_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="does not match the manifest"):
        verify(_folder(tmp_path, tamper=True), None)


def test_a_model_trained_on_other_data_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="different data"):
        verify(_folder(tmp_path, data_hash="e" * 64), "d" * 64)


def test_comparison_lines_up_old_and_new_metrics():
    old = {"metrics": {"test_accuracy": 0.9608}, "framework_versions": {"torch": "2.6.0"}}
    new = {"metrics": {"test_accuracy": 0.9608}, "framework_versions": {"torch": "2.6.0+cpu"},
           "training": {"environment": "cloud-job"}}
    text = "\n".join(compare(new, old))
    assert "test_accuracy" in text and "0.9608" in text and "cloud-job" in text
