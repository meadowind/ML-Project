"""Regression tests fed by the deliberate-failure demo (infra/failure_demo.sh).

Real non-leaf photos: with the guard off the classifier gives them a disease label; the guard
must reject the ones it can. The brick wall is a documented gap (colour-based guard).
"""
from pathlib import Path

import pytest

from src.model.validator import InputValidator

CASES = Path(__file__).parent / "failure_cases"
REJECTED = ["paper_sheet.jpg", "glass.jpg"]


@pytest.mark.parametrize("name", REJECTED)
def test_known_non_leaf_photo_is_rejected(name):
    result, image = InputValidator().validate_file(CASES / name)
    assert result.status == "REJECTED_OOD_NON_LEAF" and image is None


@pytest.mark.parametrize("name", REJECTED)
def test_guard_off_lets_the_same_photo_through(name):
    result, _ = InputValidator(enable_ood_check=False).validate_file(CASES / name)
    assert result.is_valid


@pytest.mark.xfail(strict=True, reason="Known limit: the colour guard accepts brown/dark non-leaves (README)")
def test_brick_wall_is_rejected():
    result, _ = InputValidator().validate_file(CASES / "brick_wall.jpg")
    assert result.status == "REJECTED_OOD_NON_LEAF"