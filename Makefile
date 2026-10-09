SHELL := /bin/bash
IMAGE ?= lemon-batch
TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
GIT_COMMIT ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
PLATFORM ?= linux/amd64

.PHONY: setup data train test lint portability-audit validator-audit scan-secrets image clean lock lock-cloud lock-train

setup:
	python -m pip install -r requirements.txt -r requirements-dev.txt
data:
	python src/data/download_and_prep.py
train:
	MODEL_OUT_DIR=reports/repro/lemon_classifier python src/model/train.py
test:
	pytest -q tests/
lint:
	ruff check src/ cloudlayer/ scripts/ tests/
portability-audit:
	python scripts/portability_audit.py
validator-audit: ## false-reject rate of the input validator on the clean train+validation photos
	python -m src.model.eval_validator
scan-secrets:
	python scripts/scan_secrets.py
image:
	docker buildx build --platform $(PLATFORM) --build-arg GIT_COMMIT=$(GIT_COMMIT) -t $(IMAGE):$(TAG) --load .
clean:
	rm -rf reports/repro .pytest_cache .ruff_cache
lock:
	uv pip compile requirements-runtime.in --generate-hashes \
	  --python-version 3.11 --python-platform x86_64-manylinux_2_28 \
	  --index-url https://download.pytorch.org/whl/cpu \
	  --extra-index-url https://pypi.org/simple \
	  --index-strategy unsafe-best-match \
	  -o requirements-runtime.lock

lock-cloud:
	uv pip compile requirements-cloud.in -c requirements-runtime.lock --generate-hashes \
	  --python-version 3.11 --python-platform x86_64-manylinux_2_28 \
	  -o requirements-cloud.lock

lock-train:
	grep -E '^[A-Za-z0-9_.-]+==' requirements-runtime.lock | cut -d' ' -f1 | grep -vi '^fsspec==' > .train-constraints.tmp
	uv pip compile requirements-train.in -c .train-constraints.tmp --generate-hashes \
	  --python-version 3.11 --python-platform x86_64-manylinux_2_28 -o .train-extras.tmp
	python scripts/merge_locks.py requirements-runtime.lock .train-extras.tmp -o requirements-train.lock
	rm -f .train-constraints.tmp .train-extras.tmp

include make/batch.mk
