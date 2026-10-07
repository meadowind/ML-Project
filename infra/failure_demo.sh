#!/usr/bin/env bash
# Deliberate-failure demo: score the SAME non-leaf photos with the OOD guard OFF and ON.
#
#   make image
#   bash infra/failure_demo.sh path/to/folder_of_non_leaf_photos
#
# Shows that a softmax classifier happily gives a confident disease label to a photo of
# something that is not a leaf, and that the validator (guard ON) is what stops it.
set -euo pipefail
cd "$(dirname "$0")/.."
SRC="${1:?usage: failure_demo.sh <folder of non-leaf photos>}"

for mode in off on; do
  flag=$([ "$mode" = off ] && echo false || echo true)
  dir="data_demo_${mode}"
  rm -rf "$dir"; mkdir -p "$dir/intake"
  cp "$SRC"/* "$dir/intake/"
  make run-batch-local DATA="$PWD/$dir" ENABLE_OOD_CHECK="$flag" BATCH_ID="failure-ood-$mode" >/dev/null
done

python - <<'PY'
import csv
rows = {}
for mode in ("off", "on"):
    with open(f"data_demo_{mode}/output/results/failure-ood-{mode}.csv", encoding="utf-8") as fh:
        rows[mode] = {r["filename"]: r for r in csv.DictReader(fh)}
print(f"{'file':<28}{'guard OFF':<38}{'guard ON'}")
for name in sorted(rows["off"]):
    a, b = rows["off"][name], rows["on"][name]
    left = f"{a['predicted_class'] or a['status']} ({a['confidence'] or '-'})"
    print(f"{name:<28}{left:<38}{b['status']}")
PY
