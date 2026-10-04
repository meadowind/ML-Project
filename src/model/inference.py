"""
Shared inference utility for batch inference and testing.
"""

import json
from pathlib import Path
from typing import List, Tuple
from PIL import Image
import torch
from torchvision import transforms

TRANSFORM = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def load_model(registry_dir: Path) -> Tuple[torch.jit.ScriptModule, List[str], dict]:
    model_path = registry_dir / "model.torchscript.pt"
    manifest_path = registry_dir / "model_manifest.json"

    if not model_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(f"Model artifacts not found in {registry_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    model = torch.jit.load(str(model_path), map_location="cpu")
    model.eval()
    return model, manifest["classes"], manifest

def predict(image: Image.Image, model: torch.jit.ScriptModule, classes: List[str]) -> Tuple[str, float]:
    tensor = TRANSFORM(image.convert("RGB")).unsqueeze(0)
    with torch.no_grad():
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1).squeeze(0)
        confidence, class_idx = torch.max(probs, dim=0)

    return classes[class_idx.item()], float(confidence.item())