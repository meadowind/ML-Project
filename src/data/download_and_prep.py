"""
Dataset intake, stratified partitioning, and lineage fingerprinting.
Dataset: Project-AgML/lemon_leaf_disease_classification (CC BY 4.0)
"""

import hashlib
import json
import logging
import shutil
from pathlib import Path
from datasets import load_dataset
from PIL import Image
from sklearn.model_selection import train_test_split

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Base paths relative to this script
PROJECT_ROOT = Path(__file__).resolve().parents[2]
HF_DATASET_REPO = "Project-AgML/lemon_leaf_disease_classification"
PINNED_REVISION = "04a1183c2c2902ef52ca73171a190f75f1e2dbfa"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
METADATA_FILE = PROJECT_ROOT / "data" / "dataset_lineage.json"

EXPECTED_CLASSES = [
    "Anthracnose",
    "Bacterial_Blight",
    "Citrus_Canker",
    "Curl_Virus",
    "Deficiency_Leaf",
    "Dry_Leaf",
    "Healthy_Leaf",
    "Sooty_Mould",
    "Spider_Mites",
]

def compute_dataset_hash(directory: Path) -> str:
    hasher = hashlib.sha256()
    for file_path in sorted(directory.rglob("*.jpg")):
        hasher.update(file_path.name.encode("utf-8"))
        hasher.update(file_path.read_bytes())
    return hasher.hexdigest()

def download_and_prep_stratified():
    logger.info("Loading pinned dataset: %s @ %s", HF_DATASET_REPO, PINNED_REVISION)
    raw_dataset = load_dataset(HF_DATASET_REPO, revision=PINNED_REVISION)

    all_images = []
    all_labels = []
    for split_key in raw_dataset.keys():
        for record in raw_dataset[split_key]:
            all_images.append(record["image"])
            all_labels.append(EXPECTED_CLASSES[record["label"]])

    total_samples = len(all_labels)
    logger.info("Aggregated %d total samples across upstream partitions.", total_samples)

    # Stratified Split: 70% Train, 15% Validation, 15% Test with deterministic seed
    indices = list(range(total_samples))
    train_idx, temp_idx, _, y_temp = train_test_split(
        indices, all_labels, test_size=0.30, random_state=42, stratify=all_labels
    )
    val_idx, test_idx = train_test_split(
        temp_idx, test_size=0.50, random_state=42, stratify=y_temp
    )

    splits = {
        "train": train_idx,
        "validation": val_idx,
        "test": test_idx,
    }

    if PROCESSED_DIR.exists():
        shutil.rmtree(PROCESSED_DIR)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    split_counts = {s: {cls: 0 for cls in EXPECTED_CLASSES} for s in splits}

    for split_name, split_indices in splits.items():
        split_dir = PROCESSED_DIR / split_name
        for cls in EXPECTED_CLASSES:
            (split_dir / cls).mkdir(parents=True, exist_ok=True)

        for i, sample_idx in enumerate(split_indices):
            img: Image.Image = all_images[sample_idx]
            cls_name = all_labels[sample_idx]
            # Unique filename avoids any potential overwrite collisions
            file_name = f"{split_name}_{cls_name}_{i:04d}.jpg"
            img_path = split_dir / cls_name / file_name
            img.convert("RGB").save(img_path, format="JPEG", quality=95)
            split_counts[split_name][cls_name] += 1

    fingerprint = compute_dataset_hash(PROCESSED_DIR)

    lineage = {
        "dataset_name": "Lemon Leaf Disease Classification",
        "huggingface_repo": HF_DATASET_REPO,
        "revision_pinned": PINNED_REVISION,
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Dataset provided by Project-AgML on Hugging Face. Used under CC BY 4.0.",
        "modifications": "Re-saved to 95% JPEG, partitioned into stratified 70/15/15 splits, unified folder hierarchy.",
        "random_seed": 42,
        "splits": split_counts,
        "processed_dir_sha256": fingerprint,
    }

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(lineage, f, indent=2)

    logger.info("Dataset prepared. Fingerprint: %s", fingerprint)

if __name__ == "__main__":
    download_and_prep_stratified()
    