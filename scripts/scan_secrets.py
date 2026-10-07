"""Lab 4 — secret scan, full git history.

    python scripts/scan_secrets.py

Runs gitleaks against the *entire* commit history, not just the working tree. A key that
was committed and later deleted is still disclosed — git history does not forget, and a
scan that only checks the current checkout would miss it entirely.

This is deliberately the first step in ci.yml, ahead of even lint: it is the only failure
in the pipeline that a later commit cannot undo. Once a key is pushed it is disclosed, and
reverting is theatre.

Refuses to run on a shallow checkout. actions/checkout@v4 defaults to fetch-depth: 1,
which means gitleaks would only ever see the single most recent commit — a repository
full of leaked keys in its history would scan clean. ci.yml must set `fetch-depth: 0`
for this check to mean anything; see the checkout step there.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _is_shallow_clone() -> bool:
    """True if this checkout's history has been truncated (e.g. fetch-depth: 1)."""
    result = subprocess.run(
        ["git", "rev-parse", "--is-shallow-repository"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip() == "true"


def _gitleaks_available() -> bool:
    return shutil.which("gitleaks") is not None


def main() -> int:
    if _is_shallow_clone():
        print(
            "REFUSING TO SCAN: this is a shallow git checkout (truncated history).\n"
            "A shallow scan only sees the most recent commit, so a key committed and\n"
            "later deleted would never be found — the scan would pass on a repository\n"
            "full of leaked keys.\n\n"
            "Fix: in ci.yml, set `fetch-depth: 0` on the actions/checkout step so the\n"
            "full history is available before this script runs.\n\n"
            "Locally: run `git fetch --unshallow` if this clone was made shallow, or\n"
            "just clone normally (no --depth flag).",
            file=sys.stderr,
        )
        return 2

    if not _gitleaks_available():
        print(
            "gitleaks is not installed or not on PATH.\n"
            "Install: https://github.com/gitleaks/gitleaks#installing\n"
            "In CI this is done via the gitleaks GitHub Action or a direct binary\n"
            "download step placed before this script runs.",
            file=sys.stderr,
        )
        return 2

    report_path = REPO_ROOT / "reports" / "gitleaks-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "gitleaks", "detect",
        "--source", str(REPO_ROOT),
        "--report-format", "json",
        "--report-path", str(report_path),
        "--redact",            # do not print the actual secret value to logs
        "--no-banner",
        "-v",
    ]
    result = subprocess.run(cmd)

    # gitleaks exit codes: 0 = clean, 1 = leaks found, anything else = tool error.
    if result.returncode == 0:
        print("OK  no secrets found in git history")
        return 0

    if result.returncode == 1:
        findings = []
        if report_path.exists():
            try:
                findings = json.loads(report_path.read_text())
            except json.JSONDecodeError:
                pass
        print(f"\nALERT  {len(findings)} potential secret(s) found in git history.", file=sys.stderr)
        for f in findings:
            print(
                f"  - rule={f.get('RuleID')} file={f.get('File')} "
                f"commit={f.get('Commit', '')[:8]} line={f.get('StartLine')}",
                file=sys.stderr,
            )
        print(
            f"\nFull report: {report_path}\n"
            "A committed secret is disclosed the moment it is pushed, even if you "
            "delete it in the next commit. Rotate the credential; do not just remove "
            "the line.",
            file=sys.stderr,
        )
        return 1

    print(f"gitleaks exited with an unexpected code: {result.returncode}", file=sys.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
