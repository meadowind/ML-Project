"""Merge a base uv lock with an extras lock into one hash-locked file.

    python scripts/merge_locks.py requirements-runtime.lock extras.lock -o requirements-train.lock

Both inputs are `uv pip compile --generate-hashes` outputs. A package present in both keeps the
extras version (the extras were resolved against the base, so they only differ where an extra
needs another version, e.g. fsspec). Everything else is copied block by block, hashes intact,
so `pip install --require-hashes -r <merged>` stays fully hash-checked in a single install.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BLOCK_START = re.compile(r"^([A-Za-z0-9_.-]+)==\S+ \\?$")


def parse(text: str) -> dict[str, str]:
    """name -> the package's whole block (requirement line, hash lines, '# via' comments)."""
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        match = BLOCK_START.match(line)
        if match:
            current = match.group(1).lower().replace("_", "-")
            blocks[current] = [line]
        elif current and (line.startswith((" ", "\t"))):
            blocks[current].append(line)
        else:
            current = None  # comment or blank line between blocks
    return {name: "\n".join(lines) for name, lines in blocks.items()}


def merge(base: str, extras: str) -> str:
    merged = parse(base)
    merged.update(parse(extras))
    header = (
        "# Merged by scripts/merge_locks.py (see `make lock-train`): the base lock plus the\n"
        "# extras lock; where both name a package the extras version wins. Do not edit by hand.\n"
    )
    return header + "\n".join(merged[name] for name in sorted(merged)) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("base", type=Path)
    ap.add_argument("extras", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args(argv)
    args.output.write_text(
        merge(args.base.read_text(encoding="utf-8"), args.extras.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
