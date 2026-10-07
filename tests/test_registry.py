"""Registry lineage + round trip through LocalAdapter (no cloud, no torch)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from register_model import build_lineage, register, sha256_file
from reload_check import pick_images, verify_files

from cloudlayer.base import LocalAdapter
from cloudlayer.gcp import _label_value

DIGEST = "reg/lemon-batch@sha256:" + "a" * 64


def _model_dir(tmp_path, tamper=False):
    d = tmp_path / "reg"
    d.mkdir()
    (d / "model.torchscript.pt").write_bytes(b"weights")
    m = {"git_commit": "abc", "version": "v2.0.0", "mlflow_run_id": "r1",
         "hyperparameters": {"seed": 42},
         "dataset_lineage": {"processed_dir_sha256": "d" * 64, "revision_pinned": "rev1"},
         "metrics": {"best_val_accuracy": 0.94, "test_accuracy": 0.941},
         "artifacts": {"torchscript_sha256": "0" * 64 if tamper else sha256_file(d / "model.torchscript.pt")}}
    (d / "model_manifest.json").write_text(json.dumps(m))
    return d


def _adapter(tmp_path):
    return LocalAdapter(SimpleNamespace(data_dir=str(tmp_path / "data")))


def test_lineage_requires_digest():
    with pytest.raises(ValueError):
        build_lineage({}, "reg/lemon-batch:latest")


def test_lineage_is_flat_strings():
    ln = build_lineage({"git_commit": "abc", "metrics": {"test_accuracy": 0.9}}, DIGEST)
    assert ln["image_digest"] == "sha256:" + "a" * 64 and ln["metric_test"] == "0.9"
    assert all(isinstance(v, str) for v in ln.values())


def test_register_and_fetch_roundtrip(tmp_path):
    ad = _adapter(tmp_path)
    d = _model_dir(tmp_path)
    ref = register(ad, d, DIGEST, "lemon")
    assert ref == "lemon@1"
    out = tmp_path / "out"
    lineage = ad.fetch_model("lemon", str(out))
    assert lineage["git_commit"] == "abc" and lineage["seed"] == "42"
    assert lineage["data_version"] == "d" * 64 and lineage["model_version"] == "v2.0.0"
    verify_files(out)


def test_register_rejects_tampered_model(tmp_path):
    with pytest.raises(ValueError):
        register(_adapter(tmp_path), _model_dir(tmp_path, tamper=True), DIGEST, "lemon")


def test_second_registration_is_new_version(tmp_path):
    ad = _adapter(tmp_path)
    d = _model_dir(tmp_path)
    register(ad, d, DIGEST, "lemon")
    (d / "model.torchscript.pt").write_bytes(b"v2")
    m = json.loads((d / "model_manifest.json").read_text())
    m["artifacts"]["torchscript_sha256"] = sha256_file(d / "model.torchscript.pt")
    (d / "model_manifest.json").write_text(json.dumps(m))
    assert register(ad, d, DIGEST, "lemon") == "lemon@2"


def test_pick_images_spreads_classes(tmp_path):
    for c in ("a", "b", "c"):
        (tmp_path / c).mkdir()
        for i in range(3):
            (tmp_path / c / f"{i}.jpg").write_bytes(b"x")
    picks = pick_images(tmp_path, 5)
    assert len(picks) == 5 and {p.parent.name for p in picks} == {"a", "b", "c"}


def test_label_value_sanitised():
    v = _label_value("Sha256:ABC.def/" + "x" * 100)
    assert len(v) <= 63 and v == v.lower() and all(c.isalnum() or c in "_-" for c in v)
