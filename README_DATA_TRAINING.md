# Data and training

How the dataset is obtained and prepared, how the model is trained, and how to reproduce it.
The operational side (batch job, schedule, monitoring) is in `README.md`; the model's results and
limits are in `docs/MODEL_CARD.md`; the files the batch job writes are in `docs/DATA_CONTRACT.md`.

## Dataset

| | |
|---|---|
| Name | Lemon Leaf Disease Classification |
| Source | Hugging Face, `Project-AgML/lemon_leaf_disease_classification` |
| Revision | pinned to commit `04a1183c2c2902ef52ca73171a190f75f1e2dbfa` |
| License | CC BY 4.0. Dataset provided by Project-AgML on Hugging Face; used under CC BY 4.0 |
| Size | 1,354 photos, 9 classes |
| Classes | Anthracnose, Bacterial_Blight, Citrus_Canker, Curl_Virus, Deficiency_Leaf, Dry_Leaf, Healthy_Leaf, Sooty_Mould, Spider_Mites |
| Modifications | re-saved as 95% quality JPEG, re-partitioned into stratified 70/15/15 splits, one folder per split and class |

The photos are not stored in git. `make data` downloads the pinned revision (about 360 MB) and
rebuilds them. What *is* committed is `data/dataset_lineage.json`: the revision, the license text, the
number of photos per split and class, and a SHA-256 fingerprint of the processed folder
(`de9e6aae1591644ac14a7f50e27a003eb3fec5f37318a40d3058b86b67452630`). The fingerprint is computed over
the sorted file names and bytes of every `.jpg`. Training compares it with the committed one, so "same
data" is checked, not assumed.

### Preparation (`src/data/download_and_prep.py`)
1. Load all upstream partitions of the pinned revision and pool them (1,354 photos).
2. Split with `train_test_split`, `random_state=42`, stratified by class: 70% train, then the
   remaining 30% split in half into validation and test.
3. Save each photo as `data/processed/<split>/<class>/<split>_<class>_<nnnn>.jpg`, JPEG quality 95.
4. Write `data/dataset_lineage.json` with the counts and the fingerprint.

| Split | Photos | Smallest class | Largest class |
|---|---|---|---|
| train | 947 | Anthracnose (70) | Healthy_Leaf (147) |
| validation | 203 | Anthracnose (15) | Healthy_Leaf (31) |
| test | 204 | Anthracnose (15) | Healthy_Leaf (32) |

The classes are imbalanced (70 to 147 training photos). We did not rebalance or reweight; the test
split keeps the same proportions, and the model card reports recall per class.

## Model and training (`src/model/train.py`)

| | |
|---|---|
| Architecture | MobileNetV3-Small from torchvision, ImageNet pre-trained weights, last layer replaced by a 9-way linear layer |
| Input | RGB resized to 224x224, ImageNet mean/std normalisation |
| Train augmentation | random horizontal flip only |
| Optimiser | AdamW, learning rate 1e-3, batch size 32, 5 epochs, CPU only |
| Seed | 42 (Python, NumPy and PyTorch) |
| Model selection | the epoch with the best validation accuracy is kept; the test split is evaluated once, at the end, and never used to choose anything |
| Output | `weights.pt`, `model.torchscript.pt` and `model_manifest.json` |

`model_manifest.json` records the version, git commit, framework versions, hyper-parameters, class
list, all metrics (accuracy, macro F1, recall per class, confusion matrix, share of clean test photos
below confidence 0.60), the dataset lineage, the SHA-256 of both model files, and `training`: where it
was trained (`cloud-job` or local), the digest of the training image and the Vertex AI job id. Each
run is also tracked in MLflow (parameters, metrics, the files as artifacts) and registered with the alias
`candidate`; the MLflow run id is stored in the manifest.

The pre-trained starting weights are downloaded by torchvision at training time (the file name
carries a hash prefix) and are not stored in our bucket. If that download were unavailable, training
could not start; the committed model in `models/registry/` is unaffected.

### Reproducibility
The seed, data revision, data fingerprint and library versions (hash-locked in
`requirements-train.lock`) are fixed. The result still depends on the PyTorch version and on the CPU
architecture: the same data and seed gave 94.1% test accuracy under PyTorch 2.14.0, 96.1% under
2.6.0 on an arm64 laptop, and 95.1% under 2.6.0 on x86-64 (Vertex AI, and the amd64 container on a
laptop). `make reproduce` checks the last one; the tolerance and its reasoning are in `README.md`
("Reproduce the model") and `docs/MODEL_CARD.md`.

## How to run it

First time, with Python 3.11:
```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1
make setup                         # pinned dependencies
```

| Command | What it does |
|---|---|
| `make data` | download the pinned revision, build `data/processed/`, rewrite `data/dataset_lineage.json` |
| `make train` | train locally; writes to `reports/repro/lemon_classifier/`, never over the committed model |
| `make reproduce` | the one command for a grader: rebuild the data and retrain inside Docker with no cloud account, then `make verify` compares with the claim in `README.md` |
| `make train-cloud` | build the training image, submit it as a Vertex AI custom job, wait for it. The job refuses to train if the rebuilt data fingerprint differs from the committed one |
| `make fetch-trained RUN=<id>` | download a cloud-trained model, verify its hashes, and compare it with the committed one |
| `make fetch-trained RUN=<id> ARGS=--adopt` | copy it to `models/registry/lemon_classifier_v2/` (then open a pull request) |

If `make data` produces a different fingerprint than the committed one, stop: either the upstream
revision or the library versions changed, and every number in the model card would need to be redone.
Set `ALLOW_NEW_DATA=1` in the cloud job only if you mean to accept a different dataset.

## Input validator (`src/model/validator.py`)
Before a photo is scored, the batch job screens it. A photo that fails is not scored; it is copied to
`quarantine/` with a status.

| Check | Rule | Status |
|---|---|---|
| Bytes | the file must open as an image | `REJECTED_CORRUPTED` |
| Resolution | at least 64x64 | `REJECTED_RESOLUTION` |
| Blur | Laplacian variance on a 256x256 version must be at least 65.0 | `REJECTED_BLURRED` |
| Plant tissue | at least 5% of pixels in a foliage-green, necrotic-brown or soot-black colour range | `REJECTED_OOD_NON_LEAF` |

The ranges include brown and black on purpose so that real Dry_Leaf and Sooty_Mould leaves are not
rejected (0.00% false rejects on the clean training and validation photos, see the model card). The
price is that dark or brown objects can pass; this is the failure documented in `README.md` ("The
failure we designed for").

## Where things are
```
data/dataset_lineage.json     committed: revision, license, split counts, fingerprint
data/processed/               not committed: rebuilt by `make data`
src/data/download_and_prep.py dataset intake and splits
src/model/train.py            training, evaluation, manifest, MLflow
src/model/validator.py        input screening
scripts/train_job.py          entry point inside the cloud training container
models/registry/              the committed model that the batch image serves
reports/reproduce/            output of `make reproduce` (not committed)
```
