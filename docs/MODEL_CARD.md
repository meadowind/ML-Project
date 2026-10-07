# Model Card: Lemon Leaf Disease Classifier (v2.0.0)

## Model Details
- **Model Version:** v2.0.0
- **Training Date:** October 2026
- **Architecture:** MobileNetV3-Small (Transfer Learning), 9 classes
- **Deployment Format:** TorchScript CPU Artifact (`model.torchscript.pt`) with `model_manifest.json`
- **Training environment:** PyTorch 2.6.0 (CPU), the same version as the serving image
- **License:** CC BY 4.0

## Intended Use
- **Primary Use:** Scheduled batch inference classifying lemon leaf uploads to identify non-healthy foliage and flag them as "needs inspection" for manual tree checking.
- **Out of Scope:** Real-time drone spray guidance or diagnosing non-citrus plants. The model is a triage aid, not a diagnosis: a leaf it calls *Healthy* has not been cleared.

## Dataset & Attribution
- **Source:** Hugging Face `Project-AgML/lemon_leaf_disease_classification`
- **Pinned Commit Hash:** `04a1183c2c2902ef52ca73171a190f75f1e2dbfa`
- **License:** Creative Commons Attribution 4.0 International ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/))
- **Attribution Statement:** "Dataset provided by Project-AgML on Hugging Face. Used under CC BY 4.0."
- **Processed-data fingerprint:** `de9e6aae1591644ac14a7f50e27a003eb3fec5f37318a40d3058b86b67452630` (`data/dataset_lineage.json`)
- **Modifications:** Images were re-saved as 95% quality JPEGs, reorganized into stratified splits, resized to 224x224 during inference, and augmented with blurred and corrupted copies for pipeline failure injection testing.

## Training Splits (Stratified 70 / 15 / 15, Seed 42)
- Train: 947 images (70%)
- Validation: 203 images (15%)
- Test: 204 images (15%)
- Total: 1,354 images across 9 classes

## Test Evaluation Metrics (Held-Out Test Set, 204 images)
- **Accuracy:** 96.1% (196 / 204)
- **Macro F1 Score:** 0.961
- **Best validation accuracy** (used to pick the saved epoch; the test set was not used for selection): 95.6%
- **Clean Test Images with Confidence < 0.60:** 1.47% (baseline for the 30% low-confidence alert threshold)
- **Validator False-Reject Rate:** 0.00% across clean training and validation sets

| Class | Recall (test) |
|---|---|
| Anthracnose | 1.000 |
| Bacterial_Blight | 1.000 |
| Citrus_Canker | 1.000 |
| Curl_Virus | 0.941 |
| Deficiency_Leaf | 0.897 |
| Dry_Leaf | 1.000 |
| Healthy_Leaf | 1.000 |
| Sooty_Mould | 0.826 |
| Spider_Mites | 1.000 |

With 204 test images, one image is about 0.5 percentage points: differences of a point or two between runs are within noise.

## Reproducibility
Seed, data revision and data hash are pinned, and each run is recorded in MLflow (run id stored in the manifest and in the registry lineage). Results are reproducible **for the same PyTorch version**. Retraining the same data and seed under a different PyTorch version gave different numbers: the earlier v2.0.0 model, trained under PyTorch 2.14.0, scored 94.1% accuracy / 0.943 macro F1 on the same test set (identical data hash); the current model, trained under 2.6.0, scores 96.1% / 0.961 (Curl_Virus and Spider_Mites recall improved, Deficiency_Leaf dropped from 0.931 to 0.897, Sooty_Mould unchanged at 0.826). It was adopted because the data was identical, the aggregate metrics did not get worse, and its training version matches the serving image.

## Input Validation Guardrails
Pre-inference screening via `InputValidator` (`src/model/validator.py`):
1. **Byte Integrity:** PIL byte validation against malformed uploads.
2. **Normalized Blur Threshold:** Laplacian variance on 256x256 scaled images (cutoff: 65.0).
3. **Broadened Plant Envelope:** Union of foliage green, necrotic brown (Dry Leaf), and charcoal soot (Sooty Mould). Rejects uploads under 5% plant tissue.
4. **Toggles:** Supports `enable_blur_check` and `enable_ood_check` flags for deliberate failure demonstration.

## Limitations & Risks
- **Diseased leaves can be called Healthy, confidently.** Sooty_Mould recall is 0.826 (4 of 23 test leaves missed) and Deficiency_Leaf 0.897. In the live deployment, `test_Sooty_Mould_0017.jpg` was predicted *Healthy_Leaf* with confidence 0.98 — sharp photo, plenty of foliage, so no guardrail fired. The 0.60 confidence threshold cannot catch this kind of error; a manager should treat "Healthy" as "not flagged", and occasional spot checks are still needed.
- **Single Source:** Dataset reflects curated AgML collection conditions rather than diverse orchard camera angles.
- **Class Imbalance:** Training samples range from 70 images (Anthracnose) to 147 images (Healthy Leaf).
- **OOD Sensitivity:** Standard softmax layers exhibit overconfidence on non-leaf images unless guarded by `InputValidator`.
- **Small test set:** per-class recall rests on 17–29 images per class, so the table above carries wide uncertainty.

## Traceability
The production model is registered in the cloud model registry with its lineage: git commit, data fingerprint, MLflow run id, serving image digest, seed and metrics (see the README, "Model registry").
