"""`make diagnose` maps changes in batch signals to a likely cause. Pure Python, no torch."""
from __future__ import annotations

import csv

import diagnose_performance as dp
import simulate_drift_demo as sim

from src.batch.run import CSV_COLUMNS

CLASSES = ["Healthy_Leaf", "Citrus_Canker", "Dry_Leaf"]


def rows(batch: str, n: int, *, status: str = "SCORED", conf: float = 0.90, blur: float = 150.0,
         foliage: float = 0.45, classes: list[str] | None = None, hour: int = 9) -> list[dict]:
    """n photos with small deterministic variation so distributions are not degenerate."""
    classes = classes or CLASSES
    out = []
    for i in range(n):
        out.append({
            "batch_id": batch, "filename": f"{batch}-{i}.jpg", "status": status,
            "predicted_class": classes[i % len(classes)] if status == "SCORED" else "",
            "confidence": f"{min(conf + (i % 5) * 0.01, 0.999):.3f}" if status == "SCORED" else "",
            "needs_inspection": "false", "model_version": "v2.1.0",
            "blur_score": f"{blur + (i % 7) * 3:.1f}", "foliage_ratio": f"{foliage + (i % 6) * 0.01:.3f}",
            "rejection_reason": "", "processed_at": f"2026-10-1{1 if hour < 12 else 2}T{hour:02d}:00:00Z",
        })
    return out


def stable_baseline() -> list[dict]:
    return rows("batch-20261009T090000Z", 40) + rows("batch-20261009T110000Z", 40)


def causes(result: dict) -> str:
    return " ".join(result["causes"]).lower()


def test_psi_is_zero_for_identical_and_large_for_a_shift():
    assert dp.psi({"a": 50, "b": 50}, {"a": 50, "b": 50}) == 0.0
    assert dp.psi({"a": 90, "b": 10}, {"a": 10, "b": 90}) > dp.PSI_MAJOR


def test_ks_is_zero_for_identical_and_one_for_separated_samples():
    assert dp.ks_statistic([1, 2, 3, 4], [1, 2, 3, 4]) == 0.0
    assert dp.ks_statistic([1, 2, 3], [10, 11, 12]) == 1.0


def test_stable_windows_report_no_drift():
    recent = rows("batch-20261011T090000Z", 40) + rows("batch-20261011T110000Z", 40)
    result = dp.diagnose(stable_baseline(), recent)
    assert result["tested"] and not result["drift"]
    assert "no evidence of drift" in causes(result)


def test_blurred_rejections_point_at_image_quality():
    recent = (rows("batch-20261011T090000Z", 30) + rows("batch-20261011T090100Z", 20, status="REJECTED_BLURRED"))
    result = dp.diagnose(stable_baseline(), recent)
    assert result["drift"]
    assert "blurred" in causes(result)
    assert next(f for f in result["findings"] if f["signal"] == "rejected rate")["flagged"]


def test_non_leaf_rejections_point_at_out_of_domain_inputs():
    recent = rows("batch-20261011T090000Z", 30) + rows("batch-20261011T090100Z", 20, status="REJECTED_OOD_NON_LEAF")
    assert "not lemon leaves" in causes(dp.diagnose(stable_baseline(), recent))


def test_confidence_drop_with_unchanged_inputs_points_at_the_model():
    recent = rows("batch-20261011T090000Z", 40, conf=0.45) + rows("batch-20261011T110000Z", 40, conf=0.45)
    result = dp.diagnose(stable_baseline(), recent)
    text = causes(result)
    assert result["drift"]
    assert "model uncertainty" in text and "covariate" not in text


def test_changed_image_statistics_point_at_covariate_drift():
    recent = (rows("batch-20261011T090000Z", 40, blur=60.0, foliage=0.20, conf=0.55)
              + rows("batch-20261011T110000Z", 40, blur=60.0, foliage=0.20, conf=0.55))
    text = causes(dp.diagnose(stable_baseline(), recent))
    assert "covariate drift" in text
    assert "model uncertainty" not in text


def test_class_mix_shift_with_steady_confidence_is_a_population_shift():
    recent = (rows("batch-20261011T090000Z", 40, classes=["Dry_Leaf"])
              + rows("batch-20261011T110000Z", 40, classes=["Dry_Leaf", "Dry_Leaf", "Citrus_Canker"]))
    text = causes(dp.diagnose(stable_baseline(), recent))
    assert "population shift" in text


def test_small_samples_skip_distribution_tests_and_say_so():
    result = dp.diagnose(rows("batch-20261009T090000Z", 6), rows("batch-20261011T090000Z", 5))
    assert not result["tested"]
    assert any("skipped" in n for n in result["notes"])
    assert not any("PSI" in f["signal"] or "KS" in f["signal"] for f in result["findings"])


def test_no_baseline_is_reported_not_crashed():
    result = dp.diagnose([], rows("batch-20261011T090000Z", 10))
    assert any("No baseline" in n for n in result["notes"])
    assert not result["drift"]


def test_no_recent_rows_is_reported():
    result = dp.diagnose(stable_baseline(), [])
    assert result["notes"] == ["No recent batches to examine."] and not result["drift"]


def test_every_report_says_accuracy_is_not_measured():
    result = dp.diagnose(stable_baseline(), rows("batch-20261011T090000Z", 40))
    assert any("accuracy itself is not measured" in n for n in result["notes"])


def test_split_windows_by_batch_count_and_by_time():
    data = rows("batch-a", 2, hour=9) + rows("batch-b", 2, hour=10) + rows("batch-c", 2, hour=14)
    base, recent, ids = dp.split_windows(data, 1, None)
    assert ids == ["batch-c"] and len(base) == 4 and len(recent) == 2
    _, _, since_ids = dp.split_windows(data, 3, "2026-10-11T10:00:00Z")
    assert since_ids == ["batch-b", "batch-c"]


def write_csv(path, data: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(data)


def test_cli_reads_a_results_folder_and_fails_on_drift_only_when_asked(tmp_path, capsys):
    write_csv(tmp_path / "batch-20261009T090000Z.csv", rows("batch-20261009T090000Z", 40))
    write_csv(tmp_path / "batch-20261011T090000Z.csv",
              rows("batch-20261011T090000Z", 20) + rows("batch-20261011T090000Z", 20, status="REJECTED_BLURRED"))
    args = ["--results-dir", str(tmp_path), "--recent-batches", "1"]
    assert dp.main(args) == 0
    report = capsys.readouterr().out
    assert "# Performance diagnosis" in report
    assert "blurred" in report.lower()
    assert dp.main([*args, "--fail-on-drift"]) == 1


def test_cli_with_no_results_exits_2(tmp_path):
    assert dp.main(["--results-dir", str(tmp_path)]) == 2


# --- simulated demo data (scripts/simulate_drift_demo.py) --------------------------------------


EXPECTED_CAUSE = {
    "stable": "no evidence of drift",
    "bad_uploads": "blurred",
    "non_leaf": "not lemon leaves",
    "model_uncertainty": "model uncertainty",
    "covariate_drift": "covariate drift",
}


def test_every_simulated_scenario_is_diagnosed_correctly(tmp_path):
    for scenario, expected in EXPECTED_CAUSE.items():
        out = tmp_path / scenario
        sim.write(sim.build(scenario), out)
        paths = sorted((out / "results").glob("*.csv"))
        baseline, recent, _ = dp.split_windows(dp.load_rows(paths), 3, None)
        result = dp.diagnose(baseline, recent)
        assert expected in causes(result), scenario
        assert result["drift"] is (scenario != "stable"), scenario


def test_simulated_rows_are_marked_and_match_the_batch_format(tmp_path):
    path = sim.write(sim.build("stable"), tmp_path)[0]
    with path.open() as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == CSV_COLUMNS
        assert {r["model_version"] for r in reader} == {"SIMULATED"}
