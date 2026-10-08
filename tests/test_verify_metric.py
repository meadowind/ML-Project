"""`make verify` compares a fresh training run with the README claim and the committed data hash."""
from __future__ import annotations

import verify_metric

README = "intro\n\nexpected test_accuracy: 0.951 ± 0.020\n"


def manifest(acc: float, digest: str = "a" * 64) -> dict:
    return {"metrics": {"test_accuracy": acc}, "framework_versions": {"torch": "2.6.0+cpu"},
            "dataset_lineage": {"processed_dir_sha256": digest}}


def test_within_tolerance_and_same_data_passes():
    ok, lines = verify_metric.check(manifest(0.9608), README, "a" * 64)
    assert ok and "PASS" in lines[-1]


def test_accuracy_outside_tolerance_fails():
    ok, lines = verify_metric.check(manifest(0.90), README, "a" * 64)
    assert not ok and "FAIL" in lines[-1]


def test_different_data_fails_even_if_accuracy_matches():
    ok, lines = verify_metric.check(manifest(0.951, "b" * 64), README, "a" * 64)
    assert not ok and any("DIFFERENT" in line for line in lines)


def test_missing_claim_line_fails():
    ok, lines = verify_metric.check(manifest(0.951), "no claim here", "a" * 64)
    assert not ok and "no claim line" in lines[0]
