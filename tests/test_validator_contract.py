"""Contract between the batch job and the validator Member 1 wrote."""
from __future__ import annotations

import pytest

from src.model.validator import InputValidator

EXPECTED = {
    "good_leaf.jpg": "PASSED",
    "blurred_leaf.jpg": "REJECTED_BLURRED",
    "not_a_leaf.jpg": "REJECTED_OOD_NON_LEAF",
    "tiny.jpg": "REJECTED_RESOLUTION",
    "corrupt.jpg": "REJECTED_CORRUPTED",
    "empty.jpg": "REJECTED_CORRUPTED",
}


@pytest.mark.parametrize("name,status", EXPECTED.items())
def test_status_per_fixture(images, name, status):
    result, image = InputValidator().validate_file(images[name])
    assert result.status == status
    assert result.is_valid == (status == "PASSED")
    assert (image is not None) == result.is_valid


def test_disabling_ood_check_lets_non_leaf_through(images):
    """What the deliberate-failure demo relies on: with OOD off, a non-leaf is 'valid'."""
    result, _ = InputValidator(enable_ood_check=False).validate_file(images["not_a_leaf.jpg"])
    assert result.is_valid


def test_missing_file_is_rejected_not_raised(tmp_path):
    result, image = InputValidator().validate_file(tmp_path / "ghost.jpg")
    assert result.status == "REJECTED_CORRUPTED" and image is None
