"""Shared fixtures. Images are generated, never committed; torch is never needed here."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from make_fixtures import make  # noqa: E402

from src.batch.run import Components  # noqa: E402
from src.model.validator import InputValidator  # noqa: E402


@pytest.fixture(scope="session")
def images(tmp_path_factory) -> dict[str, Path]:
    return make(tmp_path_factory.mktemp("fixtures"))


@pytest.fixture()
def dirs(tmp_path) -> dict[str, Path]:
    d = {k: tmp_path / k for k in ("intake", "archive", "quarantine", "output")}
    d["intake"].mkdir()
    return d


@pytest.fixture()
def put(dirs, images):
    def _put(*names: str, as_name: str | None = None) -> None:
        for n in names:
            shutil.copy2(images[n], dirs["intake"] / (as_name or n))
    return _put


@pytest.fixture()
def comp():
    """Real InputValidator (so the quarantine rules are the real ones), fake classifier."""
    calls = {"n": 0}

    def predict(_img):
        calls["n"] += 1
        return "Anthracnose", 0.91

    c = Components(validate=InputValidator().validate_file, predict=predict,
                   model_version="test-v0", manifest={})
    c.calls = calls  # type: ignore[attr-defined]
    return c
