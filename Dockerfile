FROM python@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534 AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY requirements-runtime.lock ./
RUN pip install --default-timeout=100 --require-hashes \
      --index-url https://download.pytorch.org/whl/cpu \
      --extra-index-url https://pypi.org/simple \
      --prefix=/install -r requirements-runtime.lock
# Cloud SDK for the scheduled (Cloud Run) entry point only; pure PyPI, hash-checked, versions
# constrained to the runtime lock so nothing torch depends on moves.
COPY requirements-cloud.lock ./
RUN pip install --default-timeout=100 --require-hashes --only-binary=:all: \
      --prefix=/install -r requirements-cloud.lock

FROM python@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534 AS runtime
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=${GIT_COMMIT} PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app MODEL_DIR=/app/models/registry/lemon_classifier_v2
RUN useradd --create-home --uid 10001 runner
COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=runner:runner src/model/ ./src/model/
COPY --chown=runner:runner src/batch/ ./src/batch/
# Scheduled entry point (scripts/cloud_batch.py): sync_down -> score -> sync_up through the
# adapter. The default CMD below is unchanged, so `make run-batch-local` still works on
# local folders only, with no credentials.
COPY --chown=runner:runner src/config.py ./src/config.py
COPY --chown=runner:runner cloudlayer/ ./cloudlayer/
COPY --chown=runner:runner scripts/sync_down.py scripts/sync_up.py scripts/cloud_batch.py ./scripts/
COPY --chown=runner:runner models/registry/lemon_classifier_v2/model.torchscript.pt models/registry/lemon_classifier_v2/model_manifest.json ./models/registry/lemon_classifier_v2/
USER runner
CMD ["python", "-m", "src.batch.run"]
