"""
Dataset intake, verification, and attribution pinning for Lemon Leaf Disease Classifier.
Dataset: Project-AgML/lemon_leaf_disease_classification (CC BY 4.0)
"""

import json
import logging
import shutil
from pathlib import Path
from datasets import load_dataset
from huggingface_hub import HfApi
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Primary repository slugs on Hugging Face
CANDIDATE_REPOS = [
    "Project-AgML/lemon_leaf_disease_classification",
    "Project-AgML/lemon-leaf-disease-classification",
]

PROCESSED_DIR = Path("data/processed")
METADATA_FILE = Path("data/dataset_lineage.json")

def resolve_repo_and_sha():
    api = HfApi()
    for repo_id in CANDIDATE_REPOS:
        try:
            info = api.dataset_info(repo_id=repo_id)
            logger.info("Found repository: %s with commit SHA: %s", repo_id, info.sha)
            return repo_id, info.sha
        except Exception:
            continue
    raise RuntimeError(f"Could not connect to any candidate repos: {CANDIDATE_REPOS}")

def download_and_pin_dataset():
    repo_id, commit_sha = resolve_repo_and_sha()
    
    logger.info("Fetching pinned dataset: %s @ %s", repo_id, commit_sha)
    ds = load_dataset(repo_id, revision=commit_sha)

    if PROCESSED_DIR.exists():
        shutil.rmtree(PROCESSED_DIR)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # If the upstream dataset only contains a 'train' split, perform a deterministic 80/20 split
    if list(ds.keys()) == ["train"]:
        logger.info("Splitting single 'train' split into 80%% train and 20%% validation...")
        split_ds = ds["train"].train_test_split(test_size=0.20, seed=42)
        ds = {"train": split_ds["train"], "validation": split_ds["test"]}

    stats = {}
    
    # Extract class labels from features if available
    first_split = next(iter(ds.keys()))
    label_feature = ds[first_split].features.get("label")
    class_names = label_feature.names if hasattr(label_feature, "names") else None

    for split_key in ds.keys():
        split_name = "validation" if split_key in ["val", "valid", "test"] else split_key
        split_dir = PROCESSED_DIR / split_name
        split_dir.mkdir(parents=True, exist_ok=True)
        stats[split_name] = {}

        logger.info("Processing split: %s (%d images)...", split_name, len(ds[split_key]))
        for idx, item in enumerate(ds[split_key]):
            image: Image.Image = item["image"]
            label_val = item["label"]

            if class_names and isinstance(label_val, int):
                label_name = class_names[label_val]
            else:
                label_name = str(label_val)

            clean_label = label_name.replace(" ", "_")
            class_dir = split_dir / clean_label
            class_dir.mkdir(parents=True, exist_ok=True)

            img_path = class_dir / f"{split_name}_{idx:05d}.jpg"
            image.convert("RGB").save(img_path, format="JPEG", quality=95)
            
            stats[split_name][label_name] = stats[split_name].get(label_name, 0) + 1

    lineage_metadata = {
        "dataset_name": "Lemon Leaf Disease Classification",
        "huggingface_repo": repo_id,
        "revision_pinned": commit_sha,
        "license": "CC BY 4.0",
        "attribution": "Dataset provided by Project-AgML on Hugging Face. Used under CC BY 4.0.",
        "splits": stats,
    }

    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(lineage_metadata, f, indent=2)

    logger.info("Dataset downloaded and pinned successfully. Manifest written to %s", METADATA_FILE)

if __name__ == "__main__":
    download_and_pin_dataset()