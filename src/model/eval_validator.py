"""
Evaluates InputValidator false-rejection rate on clean plant datasets.
"""

import sys
from pathlib import Path

# Add project root to sys.path so 'src' can be imported
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from src.model.validator import InputValidator

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

def run_audit():
    validator = InputValidator()
    results = {}

    for split in ["train", "validation"]:
        split_dir = PROCESSED_DIR / split
        if not split_dir.exists():
            continue

        for cls_dir in sorted(split_dir.iterdir()):
            if not cls_dir.is_dir():
                continue
            cls_name = cls_dir.name
            if cls_name not in results:
                results[cls_name] = {"total": 0, "rejected": 0}

            for img_path in cls_dir.glob("*.jpg"):
                results[cls_name]["total"] += 1
                res, _ = validator.validate_file(img_path)
                if not res.is_valid:
                    results[cls_name]["rejected"] += 1

    print("\n--- VALIDATOR FALSE REJECTION AUDIT ---")
    print(f"{'Class':<22} | {'Total':<6} | {'Rejected':<8} | {'False Reject Rate'}")
    print("-" * 55)
    total_imgs, total_rej = 0, 0
    for cls, d in results.items():
        total_imgs += d["total"]
        total_rej += d["rejected"]
        rate = (d["rejected"] / d["total"]) * 100 if d["total"] > 0 else 0.0
        print(f"{cls:<22} | {d['total']:<6} | {d['rejected']:<8} | {rate:6.2f}%")

    overall = (total_rej / total_imgs) * 100 if total_imgs > 0 else 0.0
    print("-" * 55)
    print(f"Overall False-Reject Rate: {total_rej}/{total_imgs} ({overall:.2f}%)\n")

if __name__ == "__main__":
    run_audit()