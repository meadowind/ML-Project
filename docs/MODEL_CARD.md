# Model Card: Lemon Leaf Disease Classifier

## Model Details
- **Model Architecture:** MobileNetV3-Small transfer learning
- **Dataset:** `Project-AgML/lemon_leaf_disease_classification` (CC BY 4.0)
- **Commit Revision:** `01004ea7e9f3b15ad824e4d6bf54238e21975e5b`
- **Target Deployment:** Batch inference runner (CPU-optimized)

## Intended Use
- Triage 9 lemon foliage states (8 disease classes + Healthy Leaf) from orchard batch uploads.
- Outputs not classified as Healthy Leaf are designated for physical grower inspection.

## Validation Filters
- **Corrupted Byte Check:** PIL stream verification.
- **Laplacian Variance Threshold:** Reject images below 80.0 (blur).
- **Foliage Envelope Threshold:** Reject images with leaf chromaticity below 0.08 (OOD non-leaf images).