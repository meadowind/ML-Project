"""The committed production model must carry the lineage the rubric asks for."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

MANIFEST = Path(__file__).resolve().parents[1] / "models/registry/lemon_classifier_v2/model_manifest.json"


@pytest.fixture(scope="module")
def manifest():
    if not MANIFEST.exists():
        pytest.skip("production manifest not present")
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_has_identity_and_classes(manifest):
    assert manifest["version"] and manifest["model_name"]
    assert len(manifest["classes"]) == 9
    assert "Healthy_Leaf" in manifest["classes"], "batch job keys needs_inspection on this name"
    assert len(set(manifest["classes"])) == len(manifest["classes"])


def test_dataset_revision_is_pinned_to_a_commit(manifest):
    lineage = manifest["dataset_lineage"]
    assert re.fullmatch(r"[0-9a-f]{40}", lineage["revision_pinned"])
    assert lineage["license"]
    assert lineage["splits"]
