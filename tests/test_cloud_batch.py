"""The scheduled entry point runs sync_down -> score -> sync_up, and stops at the first failure."""
from __future__ import annotations

import cloud_batch
import pytest


@pytest.fixture()
def calls(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    log: list[tuple[str, list[str]]] = []
    codes = {"sync_down": 0, "score": 0, "sync_up": 0}

    def fake(name):
        def _step(argv=None):
            log.append((name, list(argv or [])))
            return codes[name]
        return _step

    monkeypatch.setattr(cloud_batch.sync_down, "main", fake("sync_down"))
    monkeypatch.setattr(cloud_batch.run, "main", fake("score"))
    monkeypatch.setattr(cloud_batch.sync_up, "main", fake("sync_up"))
    return log, codes


def test_runs_the_three_steps_in_order(calls, tmp_path):
    log, _ = calls
    assert cloud_batch.main([]) == 0
    assert [name for name, _ in log] == ["sync_down", "score", "sync_up"]
    assert log[0][1] == ["--data-dir", str(tmp_path)]
    assert log[2][1] == ["--data-dir", str(tmp_path)]


def test_reprocess_reaches_download_and_scoring_only(calls):
    log, _ = calls
    assert cloud_batch.main(["--reprocess"]) == 0
    by_name = dict(log)
    assert "--reprocess" in by_name["sync_down"]
    assert by_name["score"] == ["--reprocess"]
    assert "--reprocess" not in by_name["sync_up"]


@pytest.mark.parametrize("failing,ran", [
    ("sync_down", ["sync_down"]),
    ("score", ["sync_down", "score"]),
])
def test_failure_stops_the_cycle_and_nothing_is_pushed(calls, failing, ran):
    log, codes = calls
    codes[failing] = 1
    assert cloud_batch.main([]) == 1
    assert [name for name, _ in log] == ran  # sync_up never runs after a failed step


def test_upload_failure_is_reported(calls):
    _, codes = calls
    codes["sync_up"] = 1
    assert cloud_batch.main([]) == 1
