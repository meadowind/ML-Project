FROM python@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534 AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
COPY requirements-runtime.lock ./
RUN pip install --default-timeout=100 --require-hashes \
      --index-url https://download.pytorch.org/whl/cpu \
      --extra-index-url https://pypi.org/simple \
      --prefix=/install -r requirements-runtime.lock

FROM python@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534 AS runtime
ARG GIT_COMMIT=unknown
ENV GIT_COMMIT=${GIT_COMMIT} PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app MODEL_DIR=/app/models/registry/lemon_classifier_v2
RUN useradd --create-home --uid 10001 runner
COPY --from=builder /install /usr/local
WORKDIR /app
COPY --chown=runner:runner src/model/ ./src/model/
COPY --chown=runner:runner models/registry/lemon_classifier_v2/model.torchscript.pt models/registry/lemon_classifier_v2/model_manifest.json ./models/registry/lemon_classifier_v2/
USER runner
CMD ["python", "-c", "import torch, cv2, PIL; print(torch.__version__, cv2.__version__)"]
