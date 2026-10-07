SHELL := /bin/bash
IMAGE ?= lemon-batch
TAG ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo dev)
GIT_COMMIT ?= $(shell git rev-parse HEAD 2>/dev/null || echo unknown)
PLATFORM ?= linux/amd64

.PHONY: setup data train test lint portability-audit scan-secrets image clean lock

setup:
	python -m pip install -r requirements.txt -r requirements-dev.txt
data:
	python src/data/download_and_prep.py
train:
	MODEL_OUT_DIR=reports/repro/lemon_classifier python src/model/train.py
test:
	pytest -q tests/
lint:
	ruff check src/ scripts/ tests/
portability-audit:
	python scripts/portability_audit.py
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
