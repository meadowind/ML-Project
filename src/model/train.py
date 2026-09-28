"""
Reproducible training and artifact registry script.
"""

import json
import logging
import os
import random
import time
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SEED = 42
DATA_DIR = Path("data/processed")
MODEL_REGISTRY_DIR = Path("models/registry/lemon_classifier_v1")
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

def train_and_register():
    seed_everything(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info("Training on device: %s", device)

    train_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    train_ds = datasets.ImageFolder(DATA_DIR / "train", transform=train_tf)
    val_ds = datasets.ImageFolder(DATA_DIR / "validation", transform=val_tf)

    # On Windows, num_workers=0 avoids multi-processing spawn overhead
    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    model = models.mobilenet_v3_small(weights=models.MobileNet_V3_Small_Weights.DEFAULT)
    model.classifier[3] = nn.Linear(model.classifier[3].in_features, len(train_ds.classes))
    model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

    best_val_acc = 0.0
    start_time = time.time()

    for epoch in range(NUM_EPOCHS):
        model.train()
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()

        model.eval()
        val_correct, total = 0, 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                preds = model(images).argmax(dim=1)
                val_correct += (preds == labels).sum().item()
                total += labels.size(0)

        val_acc = val_correct / total if total > 0 else 0
        logger.info("Epoch %d/%d - Val Acc: %.4f", epoch + 1, NUM_EPOCHS, val_acc)

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            MODEL_REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
            torch.save(model.state_dict(), MODEL_REGISTRY_DIR / "weights.pt")
            scripted = torch.jit.script(model.cpu())
            scripted.save(str(MODEL_REGISTRY_DIR / "model.torchscript.pt"))
            model.to(device)

    lineage_data = {}
    if Path("data/dataset_lineage.json").exists():
        with open("data/dataset_lineage.json", "r", encoding="utf-8") as f:
            lineage_data = json.load(f)

    manifest = {
        "model_name": "lemon_leaf_classifier",
        "version": "v1.0.0",
        "architecture": "mobilenet_v3_small",
        "classes": train_ds.classes,
        "best_val_accuracy": round(best_val_acc, 4),
        "training_time_sec": round(time.time() - start_time, 2),
        "seed": SEED,
        "dataset_lineage": lineage_data,
        "artifacts": {
            "weights": "weights.pt",
            "torchscript": "model.torchscript.pt"
        }
    }

    with open(MODEL_REGISTRY_DIR / "model_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Model registered to %s with accuracy %.4f", MODEL_REGISTRY_DIR, best_val_acc)

if __name__ == "__main__":
    train_and_register()