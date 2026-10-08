"""Compare the model just trained by `make reproduce` with the claim in README.md.

    python scripts/verify_metric.py

Standard library only, so it runs on any machine. Two checks:
1. the training run used the same data: the processed-data fingerprint in the new manifest equals
   the one committed in data/dataset_lineage.json;
2. the test accuracy is within the tolerance claimed in README.md, on a line of this exact form:
       expected test_accuracy: 0.951 ± 0.020
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "reports" / "reproduce" / "lemon_classifier" / "model_manifest.json"
README = ROOT / "README.md"
LINEAGE = ROOT / "data" / "dataset_lineage.json"

CLAIM = re.compile(
    r"expected\s+test_accuracy\s*[:=]\s*(?P<value>[0-9.]+)\s*(?:±|\+/-)\s*(?P<tol>[0-9.]+)",
    re.IGNORECASE,
)


def check(manifest: dict, readme_text: str, committed_hash: str) -> tuple[bool, list[str]]:
    lines: list[str] = []
    match = CLAIM.search(readme_text)
    if not match:
        return False, ["FAIL  README.md has no claim line like: expected test_accuracy: 0.951 ± 0.020"]
    claimed, tol = float(match.group("value")), float(match.group("tol"))
    actual = float(manifest["metrics"]["test_accuracy"])
    trained_hash = manifest["dataset_lineage"]["processed_dir_sha256"]

    ok = True
    same_data = trained_hash == committed_hash
    lines.append(f"data     {'same' if same_data else 'DIFFERENT'} fingerprint ({trained_hash[:12]})")
    ok &= same_data
    delta = abs(actual - claimed)
    lines += [f"claimed  {claimed:.4f} ± {tol:.4f}", f"actual   {actual:.4f}", f"delta    {delta:.4f}",
              f"torch    {manifest['framework_versions']['torch']}"]
    ok &= delta <= tol
    lines.append("\nPASS  reproduced within tolerance" if ok else
                 "\nFAIL  data differs or accuracy is outside the claimed tolerance")
    return bool(ok), lines


def main() -> int:
    if not MANIFEST.exists():
        print("FAIL  reports/reproduce/ has no model yet — run `make reproduce` first")
        return 1
    ok, lines = check(json.loads(MANIFEST.read_text(encoding="utf-8")),
                      README.read_text(encoding="utf-8"),
                      json.loads(LINEAGE.read_text(encoding="utf-8"))["processed_dir_sha256"])
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
