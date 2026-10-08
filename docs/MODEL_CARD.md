# Model Card: Lemon Leaf Disease Classifier (v2.1.0)

## Model Details
- **Model Version:** v2.1.0 (v2.0.0 was the same architecture and data trained locally under PyTorch 2.14.0; v2.1.0 is the cloud-trained one)
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
- **Accuracy:** 95.1% (194 / 204)
- **Macro F1 Score:** 0.953
- **Best validation accuracy** (used to pick the saved epoch; the test set was not used for selection): 96.1%
- **Clean Test Images with Confidence < 0.60:** 0.49% (baseline for the 30% low-confidence alert threshold)
- **Validator False-Reject Rate:** 0.00% across clean training and validation sets

| Class | Recall (test) |
|---|---|
| Anthracnose | 1.000 |
| Bacterial_Blight | 0.875 |
| Citrus_Canker | 1.000 |
| Curl_Virus | 0.882 |
| Deficiency_Leaf | 1.000 |
| Dry_Leaf | 1.000 |
| Healthy_Leaf | 1.000 |
| Sooty_Mould | 0.783 |
| Spider_Mites | 0.941 |

With 204 test images, one image is about 0.5 percentage points: differences of a point or two between runs are within noise.

## Reproducibility
Seed, data revision and data hash are pinned, and each run is recorded in MLflow (run id stored in the manifest and in the registry lineage). The current model was trained on a Vertex AI custom job (CPU, `torch 2.6.0+cpu`, training image pinned by digest; the digest, job id and run id are in the manifest and the registry lineage), from the same data hash as every earlier model. Results depend on the PyTorch version: the earlier v2.0.0 model, trained locally under PyTorch 2.14.0, scored 94.1% accuracy / 0.943 macro F1 on this test set. Retraining under 2.6.0 on a laptop gave 96.1% / 0.961, and the cloud job under the same version gave 95.1% / 0.953 (2 images fewer correct; different CPU and thread scheduling are enough to change a few predictions). We adopted the cloud-trained model because its lineage is fully recorded (image digest, job, data hash), its validation accuracy is higher (96.1% vs 95.6%) and the test difference is within the noise noted above. Do not expect bit-identical models from two machines; expect the same data hash and metrics within about a point or two.

## Input Validation Guardrails
Pre-inference screening via `InputValidator` (`src/model/validator.py`):
1. **Byte Integrity:** PIL byte validation against malformed uploads.
2. **Normalized Blur Threshold:** Laplacian variance on 256x256 scaled images (cutoff: 65.0).
3. **Broadened Plant Envelope:** Union of foliage green, necrotic brown (Dry Leaf), and charcoal soot (Sooty Mould). Rejects uploads under 5% plant tissue.
4. **Toggles:** Supports `enable_blur_check` and `enable_ood_check` flags for deliberate failure demonstration.

## Limitations & Risks
- **Diseased leaves can be called Healthy, confidently.** On the test set 9 of the 10 errors are diseased leaves predicted *Healthy_Leaf*: 5 of 23 Sooty_Mould (recall 0.783), 2 of 16 Bacterial_Blight and 2 of 17 Curl_Virus. Because of this, 22% of the leaves the model calls Healthy are actually diseased (Healthy precision 32/41). In the live deployment, `test_Sooty_Mould_0017.jpg` was predicted *Healthy_Leaf* with confidence 0.98 by the previous model — sharp photo, plenty of foliage, so no guardrail fired. The 0.60 confidence threshold cannot catch this kind of error; a manager should treat "Healthy" as "not flagged", and occasional spot checks are still needed.
- **Single Source:** Dataset reflects curated AgML collection conditions rather than diverse orchard camera angles.
- **Class Imbalance:** Training samples range from 70 images (Anthracnose) to 147 images (Healthy Leaf).
- **OOD Sensitivity:** Standard softmax layers exhibit overconfidence on non-leaf images unless guarded by `InputValidator`.
- **Small test set:** per-class recall rests on 17–29 images per class, so the table above carries wide uncertainty.

## Traceability
The production model is registered in the cloud model registry with its lineage: git commit, data fingerprint, MLflow run id, serving image digest, seed and metrics (see the README, "Model registry").
