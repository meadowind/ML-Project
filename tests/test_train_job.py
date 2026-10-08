"""The training job refuses silently different data and publishes what it trained."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import train_job

from cloudlayer.base import LocalAdapter


def test_same_data_passes_and_different_data_stops_the_job():
    train_job.ensure_same_data("abc", "abc")
    with pytest.raises(RuntimeError, match="fingerprint changed"):
        train_job.ensure_same_data("abc", "def")


def test_different_data_can_be_accepted_explicitly(capsys):
    train_job.ensure_same_data("abc", "def", allow_new=True)
    assert "data_changed" in capsys.readouterr().out


def test_fingerprint_reads_the_lineage_file(tmp_path):
    path = tmp_path / "lineage.json"
    path.write_text(json.dumps({"processed_dir_sha256": "f" * 64}))
    assert train_job.fingerprint(path) == "f" * 64


def _adapter(tmp_path):
    return LocalAdapter(SimpleNamespace(data_dir=str(tmp_path / "data")))


def test_publish_uploads_model_files_and_extras_under_the_run(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    for name in ("model.torchscript.pt", "weights.pt", "model_manifest.json"):
        (out / name).write_bytes(b"x")
    db = tmp_path / "mlflow.db"
    db.write_bytes(b"db")
    adapter = _adapter(tmp_path)
    uri = train_job.publish(adapter, out, "train-1", extra=(db,))
    keys = adapter.list_keys("models/trained/train-1/")
    assert sorted(k.rsplit("/", 1)[1] for k in keys) == [
        "mlflow.db", "model.torchscript.pt", "model_manifest.json", "weights.pt"]
    assert uri.rstrip("/").endswith("models/trained/train-1")


def test_publish_fails_loudly_when_training_produced_no_model(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "model_manifest.json").write_bytes(b"{}")
    with pytest.raises(FileNotFoundError):
        train_job.publish(_adapter(tmp_path), out, "train-1")


def test_local_mode_trains_without_touching_the_cloud(monkeypatch, tmp_path, capsys):
    """`make reproduce` sets TRAIN_LOCAL=1: no adapter is created and nothing is published."""
    monkeypatch.setenv("TRAIN_LOCAL", "1")
    monkeypatch.setattr(train_job, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(train_job, "fingerprint", lambda *_a: "abc")
    steps = []
    monkeypatch.setattr(train_job, "run", lambda cmd, **_env: steps.append(cmd[-1]))
    monkeypatch.setattr(train_job, "publish",
                        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("must not publish")))
    assert train_job.main() == 0
    assert steps == ["src/data/download_and_prep.py", "src/model/train.py"]
    assert "trained_locally" in capsys.readouterr().out
