# Model Card: Lemon Leaf Disease Classifier (v2.1.0)

## Model Details
- **Version:** v2.1.0, October 2026. v2.0.0 was the same architecture and data trained locally under PyTorch 2.14.0; v2.1.0 is the cloud-trained model.
- **Architecture:** MobileNetV3-Small (transfer learning), 9 classes. Deployed as TorchScript CPU (`model.torchscript.pt`) with `model_manifest.json`.
- **Training:** Vertex AI custom job, PyTorch 2.6.0 (CPU), same version as the serving image. License: CC BY 4.0.

## Intended Use
Scheduled batch inference that flags lemon leaf uploads as "needs inspection" for a manual tree check. Out of scope: real-time drone spray guidance and non-citrus plants. It is a triage aid, not a diagnosis: a leaf it calls *Healthy* has not been cleared.

## Data
- **Source:** Hugging Face `Project-AgML/lemon_leaf_disease_classification`, pinned commit `04a1183c2c2902ef52ca73171a190f75f1e2dbfa`. CC BY 4.0: "Dataset provided by Project-AgML on Hugging Face. Used under CC BY 4.0."
- **Fingerprint:** `de9e6aae1591644ac14a7f50e27a003eb3fec5f37318a40d3058b86b67452630` (`data/dataset_lineage.json`).
- **Modifications:** re-saved as 95% JPEG, stratified split, resized to 224x224 at inference; blurred and corrupted copies are made separately for failure-injection tests.
- **Splits (stratified, seed 42):** train 947 / validation 203 / test 204 = 1,354 images.

## Test Results (held-out, 204 images)
- **Accuracy 95.1%** (194/204), **macro F1 0.953**. Best validation accuracy 96.1% (picks the saved epoch; test not used for selection).
- **Clean test images with confidence < 0.60:** 0.49% (baseline for the 30% low-confidence alert).
- **Validator false-reject rate:** 0/1,150 (0.00%) on clean train and validation photos (`make validator-audit`, output in `docs/evidence/validator_audit.txt`).

| Class | Recall | Class | Recall | Class | Recall |
|---|---|---|---|---|---|
| Anthracnose | 1.000 | Dry_Leaf | 1.000 | Sooty_Mould | 0.783 |
| Bacterial_Blight | 0.875 | Healthy_Leaf | 1.000 | Spider_Mites | 0.941 |
| Citrus_Canker | 1.000 | Curl_Virus | 0.882 | Deficiency_Leaf | 1.000 |

One test image is about 0.5 points, so differences of a point or two between runs are noise.

## Reproducibility
Seed, data revision and data hash are pinned; each run is logged in MLflow and recorded in the manifest and registry lineage (image digest, job id, run id). `make reproduce` retrains from the pinned data and checks the result against the README claim. Results depend on the PyTorch version (v2.0.0 under 2.14.0: 94.1%; laptop under 2.6.0: 96.1%; cloud job under 2.6.0: 95.1%), so expect the same data hash and metrics within about a point or two, not identical weights. Details: `README_DATA_TRAINING.md`.

## Guardrails (`src/model/validator.py`)
Byte integrity, resolution of at least 64x64, blur (Laplacian variance on 256x256, cutoff 65.0), and plant tissue of at least 5% (foliage green, necrotic brown or soot black). `enable_blur_check` and `enable_ood_check` flags allow deliberate failure demos.

## Limitations & Risks
- **Diseased leaves can be called Healthy, confidently.** 9 of the 10 test errors are diseased leaves predicted *Healthy_Leaf* (5 of 23 Sooty_Mould, 2 of 16 Bacterial_Blight, 2 of 17 Curl_Virus), so 22% of leaves called Healthy are diseased (precision 32/41). The 0.60 threshold cannot catch this; treat "Healthy" as "not flagged" and spot-check.
- **Single source:** curated collection conditions, not varied orchard camera angles. Training classes range from 70 (Anthracnose) to 147 (Healthy_Leaf) images.
- **Out-of-distribution:** softmax is overconfident on non-leaves; the colour guard rejects some, but brown or dark objects can pass.
- **Small test set:** per-class recall rests on 17-29 images, so it is uncertain.

## Traceability
Registered in the cloud model registry with git commit, data fingerprint, MLflow run id, image digest, seed and metrics (README, "Model registry").
