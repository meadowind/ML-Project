# Model Card: Lemon Leaf Disease Classifier (v2.0.0)

## Model Details
- **Model Version:** v2.0.0
- **Training Date:** October 2026
- **Architecture:** MobileNetV3-Small (Transfer Learning)
- **Deployment Format:** TorchScript CPU Artifact (`model.torchscript.pt`)
- **License:** CC BY 4.0

## Intended Use
- **Primary Use:** Scheduled batch inference classifying lemon leaf uploads to identify non-healthy foliage and flag them as "needs inspection" for manual tree checking.
- **Out of Scope:** Real-time drone spray guidance or diagnosing non-citrus plants.

## Dataset & Attribution
- **Source:** Hugging Face `Project-AgML/lemon_leaf_disease_classification`
- **Pinned Commit Hash:** `04a1183c2c2902ef52ca73171a190f75f1e2dbfa`
- **License:** Creative Commons Attribution 4.0 International ([CC BY 4.0](https://creativecommons.org/licenses/by/4.0/))
- **Attribution Statement:** "Dataset provided by Project-AgML on Hugging Face. Used under CC BY 4.0."
- **Modifications:** Images were re-saved as 95% quality JPEGs, reorganized into stratified splits, resized to 224x224 during inference, and augmented with blurred and corrupted copies for pipeline failure injection testing.

## Training Splits (Stratified 70 / 15 / 15, Seed 42)
- **Split Counts:**
  - Train: 946 images (70%)
  - Validation: 205 images (15%)
  - Test: 203 images (15%)
  - Total: 1,354 images across 9 classes

## Test Evaluation Metrics (Held-Out Test Set)
- **Accuracy:** ~93.6%
- **Macro F1 Score:** ~0.93
- **Clean Test Images with Confidence < 0.60:** ~3.5% (establishes baseline for Member 3's 30% low-confidence alert threshold)
- **Validator False-Reject Rate:** 0.00% across clean training and validation sets

## Input Validation Guardrails
Pre-inference screening via `InputValidator` (`src/model/validator.py`):
1. **Byte Integrity:** PIL byte validation against malformed uploads.
2. **Normalized Blur Threshold:** Laplacian variance on 256x256 scaled images (cutoff: 65.0).
3. **Broadened Plant Envelope:** Union of foliage green, necrotic brown (Dry Leaf), and charcoal soot (Sooty Mould). Rejects uploads under 5% plant tissue.
4. **Toggles:** Supports `enable_blur_check` and `enable_ood_check` flags for deliberate failure demonstration.

## Limitations & Risks
- **Single Source:** Dataset reflects curated AgML collection conditions rather than diverse orchard camera angles.
- **Class Imbalance:** Training samples range from 70 images (Anthracnose) to 147 images (Healthy Leaf).
- **OOD Sensitivity:** Standard softmax layers exhibit overconfidence on non-leaf images unless guarded by `InputValidator`.
