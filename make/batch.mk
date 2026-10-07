# Capstone batch targets. Add this line near the top of the Makefile:   include make/batch.mk
# If your Makefile already defines `cloud-check`, `image` or IMAGE, delete the duplicate there.

PYTHON ?= python
DATA    ?= $(CURDIR)/data

.PHONY: register-model reload-check cloud-check image-push sync-down sync-up run-batch run-batch-local demo-upload teardown teardown-plan

cloud-check:
	$(PYTHON) scripts/cloud_check.py

# Push the image to the registry in cloud.env; prints the digest-pinned reference.
image-push:
	$(PYTHON) -c "from cloudlayer.factory import get_adapter; from src import config; print(get_adapter(config.load()).push_image('$(IMAGE):$(TAG)'))"

sync-down:
	$(PYTHON) scripts/sync_down.py

sync-up:
	$(PYTHON) scripts/sync_up.py

# Container works on local folders only: no SDK, no credentials inside it.
# --user keeps files on the mounted volume writable by the non-root runner on Linux CI.
run-batch-local:
	docker run --rm --platform linux/amd64 --user "$$(id -u):$$(id -g)" -e HOME=/tmp \
	  -e DATA_DIR=/data $(foreach v,BLUR_THRESHOLD FOLIAGE_THRESHOLD ENABLE_BLUR_CHECK ENABLE_OOD_CHECK BATCH_ID,$(if $($(v)),-e $(v)=$($(v)))) \
	  -v "$(DATA):/data" $(IMAGE):$(TAG) python -m src.batch.run $(ARGS)

# The full scheduled cycle: pull new photos, score them, push results.
run-batch: sync-down run-batch-local sync-up

# Demo helper: simulate a grower upload.   make demo-upload FILES="a.jpg b.jpg"
demo-upload:
	$(PYTHON) scripts/upload_intake.py $(FILES)

# Deletes every bucket / registry repo labelled course=itcs355,student=<PROJECT_ID>,lab=capstone.
# Asks nothing when CONFIRM=yes. Deletion is asynchronous: re-check the console and billing.
teardown:
	@test "$(CONFIRM)" = "yes" || { echo "This DELETES the bucket and registry. Re-run: make teardown CONFIRM=yes"; exit 1; }
	$(PYTHON) -c "from cloudlayer.factory import get_adapter; from src import config; c=config.load(); print('\n'.join(get_adapter(c).teardown(c.tags('capstone'))) or 'nothing found')"

# What `make teardown` WOULD delete (resources carrying the capstone labels). Run this first.
teardown-plan:
	gcloud storage buckets list --project "$$(grep ^PROJECT_ID= cloud.env | cut -d= -f2)" --filter="labels.lab=capstone" --format="value(name)"
	gcloud artifacts repositories list --project "$$(grep ^PROJECT_ID= cloud.env | cut -d= -f2)" --location "$$(grep ^REGION= cloud.env | cut -d= -f2)" --filter="labels.lab=capstone" --format="value(name)"
	gcloud ai models list --region "$$(grep ^REGION= cloud.env | cut -d= -f2)" --project "$$(grep ^PROJECT_ID= cloud.env | cut -d= -f2)" --filter="labels.lab=capstone" --format="value(name)"

# Register the production model (needs the digest-pinned image printed by `make image-push` / CI).
#   make register-model IMAGE_REF=asia-southeast1-docker.pkg.dev/<proj>/lemon/lemon-batch@sha256:...
register-model:
	@test -n "$(IMAGE_REF)" || { echo "Set IMAGE_REF=<digest-pinned image>"; exit 1; }
	$(PYTHON) scripts/register_model.py --image "$(IMAGE_REF)"

# Pull the model back from the registry (REF=name@version, default latest) and score 5 held-out images.
reload-check:
	$(PYTHON) scripts/reload_check.py $(if $(REF),--ref $(REF),)
