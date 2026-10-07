"""Batch job behaviour: idempotency, quarantine, summaries, and never crashing on bad input."""
from __future__ import annotations

import csv
import json

import pytest

from src.batch import run as batch


def go(dirs, comp, **kw):
    return batch.run_batch(dirs["intake"], dirs["archive"], dirs["quarantine"], dirs["output"],
                           lambda: comp, **kw)


def rows(dirs, batch_id):
    with open(dirs["output"] / "results" / f"{batch_id}.csv", newline="", encoding="utf-8") as fh:
        return {r["filename"]: r for r in csv.DictReader(fh)}


def test_empty_intake_exits_without_loading_model(dirs):
    def boom():
        raise AssertionError("model must not load when there is nothing to do")

    assert batch.run_batch(dirs["intake"], dirs["archive"], dirs["quarantine"],
                           dirs["output"], boom) is None
    assert not list((dirs["output"] / "logs").glob("*")), "skipped run must not leave a log file"


def test_good_file_is_scored_and_archived(dirs, put, comp):
    put("good_leaf.jpg")
    s = go(dirs, comp, batch_id="b1")
    assert s["files_scored"] == 1 and s["files_rejected"] == 0
    assert (dirs["archive"] / "good_leaf.jpg").exists()
    r = rows(dirs, "b1")["good_leaf.jpg"]
    assert r["predicted_class"] == "Anthracnose" and r["needs_inspection"] == "true"
    assert r["model_version"] == "test-v0"


def test_intake_is_never_modified(dirs, put, comp):
    put("good_leaf.jpg", "corrupt.jpg")
    before = sorted(p.name for p in dirs["intake"].iterdir())
    go(dirs, comp, batch_id="b1")
    assert sorted(p.name for p in dirs["intake"].iterdir()) == before


def test_second_run_processes_nothing(dirs, put, comp):
    put("good_leaf.jpg", "blurred_leaf.jpg")
    assert go(dirs, comp, batch_id="b1") is not None
    n = comp.calls["n"]
    assert go(dirs, comp, batch_id="b2") is None
    assert comp.calls["n"] == n


def test_only_new_files_are_processed(dirs, put, comp):
    put("good_leaf.jpg")
    go(dirs, comp, batch_id="b1")
    put("good_leaf.jpg", as_name="second.jpg")
    s = go(dirs, comp, batch_id="b2")
    assert s["files_total"] == 1
    assert set(rows(dirs, "b2")) == {"second.jpg"}


def test_reprocess_replays_everything(dirs, put, comp):
    put("good_leaf.jpg")
    go(dirs, comp, batch_id="b1")
    s = go(dirs, comp, batch_id="b2", reprocess=True)
    assert s["files_total"] == 1


def test_bad_batch_never_crashes_and_good_files_still_scored(dirs, put, comp):
    """The designed failure: a mix of garbage must not stop the good file being scored."""
    put("good_leaf.jpg", "corrupt.jpg", "empty.jpg", "blurred_leaf.jpg", "not_a_leaf.jpg", "tiny.jpg")
    s = go(dirs, comp, batch_id="bad")
    assert s["files_total"] == 6 and s["files_scored"] == 1 and s["files_rejected"] == 5
    assert s["rejected_rate"] == pytest.approx(5 / 6, abs=1e-3)
    r = rows(dirs, "bad")
    assert r["corrupt.jpg"]["status"] == "REJECTED_CORRUPTED"
    assert r["empty.jpg"]["status"] == "REJECTED_CORRUPTED"
    assert r["blurred_leaf.jpg"]["status"] == "REJECTED_BLURRED"
    assert r["not_a_leaf.jpg"]["status"] == "REJECTED_OOD_NON_LEAF"
    assert r["tiny.jpg"]["status"] == "REJECTED_RESOLUTION"
    assert {p.name for p in dirs["quarantine"].iterdir()} == {
        "corrupt.jpg", "empty.jpg", "blurred_leaf.jpg", "not_a_leaf.jpg", "tiny.jpg"}
    assert [p.name for p in dirs["archive"].iterdir()] == ["good_leaf.jpg"]


def test_unexpected_exception_is_quarantined_not_raised(dirs, put, comp):
    put("good_leaf.jpg")

    def explode(_img):
        raise RuntimeError("model blew up")

    comp.predict = explode
    s = go(dirs, comp, batch_id="b1")
    assert s["by_status"] == {"ERROR_UNEXPECTED": 1}
    assert (dirs["quarantine"] / "good_leaf.jpg").exists()
    assert "RuntimeError" in rows(dirs, "b1")["good_leaf.jpg"]["rejection_reason"]


def test_low_confidence_rate_uses_scored_files_as_denominator(dirs, put, comp):
    put("good_leaf.jpg", "corrupt.jpg")
    comp.predict = lambda _i: ("Healthy_Leaf", 0.40)
    s = go(dirs, comp, batch_id="b1")
    assert s["low_confidence_rate"] == 1.0          # 1 of 1 scored, not 1 of 2
    assert s["needs_inspection_count"] == 0         # healthy leaf


def test_summary_and_log_are_written_and_carry_batch_id(dirs, put, comp, capsys):
    put("good_leaf.jpg")
    go(dirs, comp, batch_id="b9")
    assert json.loads((dirs["output"] / "summary" / "b9.json").read_text())["batch_id"] == "b9"
    lines = [json.loads(x) for x in (dirs["output"] / "logs" / "b9.jsonl").read_text().splitlines()]
    assert lines and all(x["batch_id"] == "b9" for x in lines)
    assert any(x["event"] == "batch_finished" for x in lines)
    assert "batch_finished" in capsys.readouterr().out


def test_missing_model_makes_main_exit_nonzero(dirs, put, tmp_path):
    put("good_leaf.jpg")
    rc = batch.main(["--intake", str(dirs["intake"]), "--archive", str(dirs["archive"]),
                     "--quarantine", str(dirs["quarantine"]), "--output", str(dirs["output"]),
                     "--model-dir", str(tmp_path / "nope")])
    assert rc == 1
