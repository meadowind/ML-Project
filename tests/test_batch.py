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
    assert s["needs_inspection_count"] == 1         # unsure "Healthy" is flagged, not trusted


def test_needs_inspection_follows_the_contract(dirs, put, comp):
    """Found live: a Sooty_Mould leaf scored Healthy at 0.54 was NOT flagged."""
    put("good_leaf.jpg", as_name="sure_healthy.jpg")
    put("good_leaf.jpg", as_name="unsure_healthy.jpg")
    put("good_leaf.jpg", as_name="sick.jpg")
    answers = {"sure_healthy.jpg": ("Healthy_Leaf", 0.99),
               "unsure_healthy.jpg": ("Healthy_Leaf", 0.5447),
               "sick.jpg": ("Sooty_Mould", 1.0)}
    comp.predict = lambda img: answers[img_name[0]]
    img_name = [""]
    orig_validate = comp.validate

    def validate(path):
        img_name[0] = path.name
        return orig_validate(path)

    comp.validate = validate
    s = go(dirs, comp, batch_id="b1")
    r = rows(dirs, "b1")
    assert r["sure_healthy.jpg"]["needs_inspection"] == "false"
    assert r["unsure_healthy.jpg"]["needs_inspection"] == "true"
    assert r["sick.jpg"]["needs_inspection"] == "true"
    assert s["needs_inspection_count"] == 2


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


def test_ood_guard_is_on_by_default_and_only_off_when_asked(monkeypatch):
    """The deliberate-failure demo turns the guard off via env. It must never be off by default."""
    monkeypatch.delenv("ENABLE_OOD_CHECK", raising=False)
    assert batch._env_flag("ENABLE_OOD_CHECK", True) is True
    monkeypatch.setenv("ENABLE_OOD_CHECK", "false")
    assert batch._env_flag("ENABLE_OOD_CHECK", True) is False
    monkeypatch.setenv("ENABLE_OOD_CHECK", "1")
    assert batch._env_flag("ENABLE_OOD_CHECK", True) is True


def test_non_leaf_scores_confidently_without_guard_but_is_quarantined_with_it(dirs, put):
    """The failure we designed for, as a regression test.

    Without the guard a classifier labels a non-leaf photo (softmax always picks something);
    with the guard the same file never reaches the model.
    """
    from src.model.validator import InputValidator

    put("not_a_leaf.jpg")

    def overconfident(_img):  # stands in for softmax, which always picks a class
        return "Anthracnose", 0.97

    unguarded = batch.Components(InputValidator(enable_ood_check=False).validate_file,
                                 overconfident, "t", {})
    s = go(dirs, unguarded, batch_id="off")
    assert s["files_scored"] == 1 and s["needs_inspection_count"] == 1   # the failure

    for d in ("archive", "quarantine", "output"):
        for p in dirs[d].rglob("*"):
            if p.is_file():
                p.unlink()
    guarded = batch.Components(InputValidator().validate_file, overconfident, "t", {})
    s = go(dirs, guarded, batch_id="on")
    assert s["files_scored"] == 0 and s["by_status"] == {"REJECTED_OOD_NON_LEAF": 1}  # the fix


def test_summary_names_rejected_samples_and_has_confidence_histogram(dirs, put, comp):
    put("good_leaf.jpg", "corrupt.jpg", "empty.jpg", "blurred_leaf.jpg",
        "not_a_leaf.jpg", "tiny.jpg")
    s = go(dirs, comp, batch_id="h1")
    samples = s["rejected_samples"]
    assert [x["filename"] for x in samples] == sorted(x["filename"] for x in samples)
    assert {x["filename"] for x in samples} >= {"corrupt.jpg", "empty.jpg", "not_a_leaf.jpg"}
    assert all(x["status"].startswith("REJECTED") for x in samples)
    assert len(samples) <= batch.REJECTED_SAMPLE_LIMIT
    hist = s["confidence_histogram"]
    assert len(hist) == batch.HISTOGRAM_BINS and sum(hist.values()) == s["files_scored"]
    assert hist["0.9-1.0"] == s["files_scored"]            # the fake classifier answers 0.91


def test_rejected_samples_are_capped(dirs, put, comp):
    for i in range(8):
        put("corrupt.jpg", as_name=f"bad{i}.jpg")
    s = go(dirs, comp, batch_id="h2")
    assert s["files_rejected"] == 8 and len(s["rejected_samples"]) == batch.REJECTED_SAMPLE_LIMIT


def test_confidence_histogram_edges():
    h = batch.confidence_histogram([0.0, 0.05, 0.6, 0.99, 1.0])
    assert h["0.0-0.1"] == 2 and h["0.6-0.7"] == 1 and h["0.9-1.0"] == 2 and sum(h.values()) == 5


def test_summary_with_no_scored_files_has_empty_histogram(dirs, put, comp):
    put("corrupt.jpg")
    s = go(dirs, comp, batch_id="h3")
    assert sum(s["confidence_histogram"].values()) == 0 and s["files_scored"] == 0
