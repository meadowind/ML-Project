"""Merging two hash locks keeps every hash and lets the extras version win."""
from __future__ import annotations

from merge_locks import merge, parse

BASE = """# header
torch==2.6.0+cpu \\
    --hash=sha256:aa
    # via -r base
fsspec==2026.9.0 \\
    --hash=sha256:bb
    # via torch
"""
EXTRAS = """fsspec==2024.12.0 \\
    --hash=sha256:cc
    # via datasets
datasets==3.3.2 \\
    --hash=sha256:dd
    # via -r extras
"""


def test_blocks_keep_their_hash_lines():
    blocks = parse(BASE)
    assert set(blocks) == {"torch", "fsspec"}
    assert "--hash=sha256:aa" in blocks["torch"]


def test_extras_win_and_nothing_is_lost():
    merged = merge(BASE, EXTRAS)
    blocks = parse(merged)
    assert set(blocks) == {"torch", "fsspec", "datasets"}
    assert "fsspec==2024.12.0" in blocks["fsspec"] and "sha256:bb" not in merged
    assert "--hash=sha256:aa" in merged and "--hash=sha256:dd" in merged
    assert merged.count("fsspec==") == 1
