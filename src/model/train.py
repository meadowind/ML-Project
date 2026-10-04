"""
Reproducible training and artifact export for lemon_classifier_v2.
"""
import hashlib
import json
import logging
import os
import random
import subprocess
import time
from pathlib import Path
import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, recall_score
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
import sys

from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data" / "processed"
MODEL_REGISTRY_DIR = PROJECT_ROOT / "models" / "registry" / "lemon_classifier_v2"

SEED = 42
BATCH_SIZE = 32
NUM_EPOCHS = 5
LEARNING_RATE = 1e-3

def seed_everything(seed: int = 42):
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True

def sha256_file(filepath: Path) -> str:
    hasher = hashlib.sha256()
    hasher.update(filepath.read_bytes())
    return hasher.hexdigest()

def get_git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "uncommitted"

def train_v2():
    seed_everything(SEED)
    device = torch.device("cpu")
    logger.info("Training device: %s", device)

    train_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    eval_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    train_ds = datasets.ImageFolder(DATA_DIR / "train", transform=train_tf)
    val_ds = datasets.ImageFolder(DATA_DIR / "validation", transform=eval_tf)
    test_ds = datasets.ImageFolder(DATA_DIR / "test", transform=eval_tf)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    classes = train_ds.classes
    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(classes))
    model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

    best_val_acc = 0.0
    start_time = time.time()

    for epoch in range(NUM_EPOCHS):
        model.train()
        for images, labels in train_loader:
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()

        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for images, labels in val_loader:
                preds = model(images).argmax(dim=1)
                correct += (preds == labels).sum().item()
                total += labels.size(0)

        val_acc = correct / total if total > 0 else 0
        logger.info("Epoch %d/%d - Val Acc: %.4f", epoch + 1, NUM_EPOCHS, val_acc)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            MODEL_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), MODEL_REGISTRY_DIR / "weights.pt")
            scripted = torch.jit.script(model)
            scripted.save(str(MODEL_REGISTRY_DIR / "model.torchscript.pt"))

    # Evaluate against the held-out test split
    best_scripted = torch.jit.load(str(MODEL_REGISTRY_DIR / "model.torchscript.pt"))
    best_scripted.eval()

    all_preds, all_targets, all_confs = [], [], []
    with torch.no_grad():
        for images, labels in test_loader:
            logits = best_scripted(images)
            probs = torch.softmax(logits, dim=1)
            confs, preds = torch.max(probs, dim=1)
            all_preds.extend(preds.numpy())
            all_targets.extend(labels.numpy())
            all_confs.extend(confs.numpy())

    test_acc = float(np.mean(np.array(all_preds) == np.array(all_targets)))
    macro_f1 = float(f1_score(all_targets, all_preds, average="macro"))
    per_class_rec = recall_score(all_targets, all_preds, average=None).tolist()
    cm = confusion_matrix(all_targets, all_preds).tolist()
    low_conf_pct = float(np.mean(np.array(all_confs) < 0.60) * 100)

    with open(PROJECT_ROOT / "data" / "dataset_lineage.json", "r", encoding="utf-8") as f:
        lineage = json.load(f)

    manifest = {
        "model_name": "lemon_leaf_classifier",
        "version": "v2.0.0",
        "training_date": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": get_git_commit(),
        "framework_versions": {
            "torch": torch.__version__,
            "numpy": np.__version__,
        },
        "hyperparameters": {
            "architecture": "mobilenet_v3_small",
            "epochs": NUM_EPOCHS,
            "batch_size": BATCH_SIZE,
            "learning_rate": LEARNING_RATE,
            "seed": SEED,
        },
        "classes": classes,
        "metrics": {
            "best_val_accuracy": round(best_val_acc, 4),
            "test_accuracy": round(test_acc, 4),
            "macro_f1": round(macro_f1, 4),
            "per_class_recall": {cls: round(rec, 4) for cls, rec in zip(classes, per_class_rec)},
            "confusion_matrix": cm,
            "clean_test_low_confidence_pct": round(low_conf_pct, 2),
        },
        "dataset_lineage": lineage,
        "artifacts": {
            "weights_pt_sha256": sha256_file(MODEL_REGISTRY_DIR / "weights.pt"),
            "torchscript_sha256": sha256_file(MODEL_REGISTRY_DIR / "model.torchscript.pt"),
        },
    }

    with open(MODEL_REGISTRY_DIR / "model_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("v2 model registered at %s", MODEL_REGISTRY_DIR)

if __name__ == "__main__":
    train_v2()