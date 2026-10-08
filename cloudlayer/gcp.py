"""GCP adapter (Layer 3) for the capstone batch pipeline.

Only what the batch job needs: blob upload/download/list, digest-pinned image push, and a
label-based teardown. Training and endpoints are not used here (scheduled batch, no
Vertex AI), so those methods inherit NotImplementedError from the base class.
Metrics/alerts (`emit_metric`) belong to the monitoring owner (Member 3).

Nothing outside cloudlayer/ may import google.* — src/ and scripts/ go through the adapter.
"""
from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from cloudlayer.base import CloudAdapter

log = logging.getLogger(__name__)

_LABEL_BAD = re.compile(r"[^a-z0-9_-]")


def _label_value(value: object) -> str:
    """GCP label values: lowercase letters, digits, '_' and '-', at most 63 chars."""
    return _LABEL_BAD.sub("_", str(value).lower())[:63]


def _storage():
    from google.cloud import storage  # imported lazily so unit tests need no SDK

    return storage


class GcpAdapter(CloudAdapter):
    # --- helpers ---------------------------------------------------------------
    def _bucket_and_prefix(self) -> tuple[str, str]:
        parsed = urlparse(self.cfg.blob_uri)
        return parsed.netloc, parsed.path.strip("/")

    def _full_key(self, key: str) -> str:
        _, prefix = self._bucket_and_prefix()
        key = key.lstrip("/")
        return f"{prefix}/{key}" if prefix else key

    def _client(self):
        return _storage().Client(project=self.cfg.project_id)

    def uri_for(self, key: str) -> str:
        bucket, _ = self._bucket_and_prefix()
        return f"gs://{bucket}/{self._full_key(key)}"

    # --- blobs -----------------------------------------------------------------
    def upload(self, local_path: str, key: str) -> str:
        bucket, _ = self._bucket_and_prefix()
        blob = self._client().bucket(bucket).blob(self._full_key(key))
        blob.upload_from_filename(local_path)
        return self.uri_for(key)

    def download(self, uri: str, local_path: str) -> None:
        parsed = urlparse(uri)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        blob = self._client().bucket(parsed.netloc).blob(parsed.path.lstrip("/"))
        blob.download_to_filename(local_path)

    def list_keys(self, prefix: str) -> list[str]:
        """Keys relative to BLOB_URI's prefix, so callers never see the bucket layout."""
        bucket, base = self._bucket_and_prefix()
        full_prefix = self._full_key(prefix)
        strip = f"{base}/" if base else ""
        keys = []
        for blob in self._client().list_blobs(bucket, prefix=full_prefix):
            if blob.name.endswith("/"):  # console-created "folder" placeholder
                continue
            keys.append(blob.name[len(strip):] if strip and blob.name.startswith(strip) else blob.name)
        return sorted(keys)

    # --- images ----------------------------------------------------------------
    def push_image(self, local_tag: str) -> str:
        registry, project_id, repo = self.cfg.container_registry.split("/")
        remote_tag = f"{registry}/{project_id}/{repo}/{local_tag}"
        subprocess.run(["gcloud", "auth", "configure-docker", registry, "--quiet"], check=True)
        subprocess.run(["docker", "tag", local_tag, remote_tag], check=True)
        subprocess.run(["docker", "push", remote_tag], check=True)
        out = subprocess.run(
            ["docker", "inspect", "--format={{index .RepoDigests 0}}", remote_tag],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip().strip("'\"")


    # --- model registry (Vertex AI Model Registry) -----------------------------
    def _aiplatform(self):
        from google.cloud import (
            aiplatform,  # lazy: only training/registry machines need it
        )

        aiplatform.init(project=self.cfg.project_id, location=self.cfg.region)
        return aiplatform

    def register_model(self, model_uri: str, name: str, lineage: dict[str, str] | None = None) -> str:
        """Register the artifacts under `model_uri` as a new version of model `name`.

        Lineage goes into labels (shortened to GCP's label rules) and, in full, into the
        version description as JSON. `lineage["image_uri"]` (digest-pinned) is required: the
        registry wants a serving image, and ours is the image that actually runs the model.
        """
        lineage = dict(lineage or {})
        image = lineage.get("image_uri")
        if not image:
            raise ValueError("lineage['image_uri'] (digest-pinned image reference) is required")
        aiplatform = self._aiplatform()
        labels = {**self.cfg.tags("capstone"),
                  **{k: _label_value(v) for k, v in lineage.items() if k != "image_uri"}}
        description = json.dumps(lineage, sort_keys=True)
        kwargs = {
            "display_name": name,
            "artifact_uri": model_uri,
            "serving_container_image_uri": image,
            "labels": labels,
            "version_aliases": ["candidate"],
        }
        existing = aiplatform.Model.list(filter=f'display_name="{name}"')
        if existing:
            kwargs["parent_model"] = existing[0].resource_name
            kwargs["version_description"] = description
        else:
            kwargs["description"] = description
        model = aiplatform.Model.upload(**kwargs)
        return f"{model.resource_name}@{model.version_id}"

    def fetch_model(self, model_ref: str, local_dir: str) -> dict[str, str]:
        """Download a registered version's artifacts and return its lineage.

        `model_ref` is the string register_model returned, or just the model name
        (meaning: the version aliased `candidate`).
        """
        aiplatform = self._aiplatform()
        if not model_ref.startswith("projects/"):
            found = aiplatform.Model.list(filter=f'display_name="{model_ref}"')
            if not found:
                raise LookupError(f"no model named {model_ref!r} in the registry")
            model_ref = f"{found[0].resource_name}@candidate"
        model = aiplatform.Model(model_name=model_ref)
        parsed = urlparse(model.uri)
        prefix = parsed.path.lstrip("/").rstrip("/") + "/"
        for blob in self._client().list_blobs(parsed.netloc, prefix=prefix):
            if blob.name.endswith("/"):
                continue
            dest = Path(local_dir) / blob.name[len(prefix):]
            dest.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(dest))
        lineage = json.loads(model.version_description or model.description or "{}")
        lineage["resolved_ref"] = model_ref
        return lineage

    # --- scheduled batch (Cloud Run job + Cloud Scheduler) -----------------------
    def _gcloud_json(self, *args: str) -> list[dict] | None:
        """Run a gcloud list command; None when it cannot run (API disabled, no permission)."""
        proc = subprocess.run(["gcloud", *args, f"--project={self.cfg.project_id}", "--format=json"],
                              capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            log.warning("gcloud %s failed, skipped: %s", " ".join(args[:3]), proc.stderr.strip()[:200])
            return None
        return json.loads(proc.stdout or "[]")

    def _teardown_scheduled_batch(self, tags: dict[str, str]) -> list[str]:
        """Delete the Cloud Scheduler entry and the Cloud Run job that run the batch.

        Cloud Run jobs are matched by labels like everything else. Scheduler entries carry no
        labels here, so they are matched by the `lemon-batch` name prefix used by
        infra/setup_cloudrun.sh. A project where either API was never enabled is skipped.
        """
        deleted: list[str] = []
        region = f"--location={self.cfg.region}"
        schedules = self._gcloud_json("scheduler", "jobs", "list", region)
        for entry in schedules or []:
            name = entry["name"]  # projects/<p>/locations/<l>/jobs/<id>
            if name.rsplit("/", 1)[-1].startswith("lemon-batch"):
                subprocess.run(["gcloud", "scheduler", "jobs", "delete", name, "--quiet",
                                f"--project={self.cfg.project_id}", region], check=True)
                deleted.append(name)
        jobs = self._gcloud_json("run", "jobs", "list", f"--region={self.cfg.region}")
        for job in jobs or []:
            meta = job.get("metadata", {})
            labels = meta.get("labels") or {}
            if all(labels.get(k) == v for k, v in tags.items()):
                subprocess.run(["gcloud", "run", "jobs", "delete", meta["name"], "--quiet",
                                f"--project={self.cfg.project_id}", f"--region={self.cfg.region}"],
                               check=True)
                deleted.append(f"run job {meta['name']}")
        return deleted

    # --- teardown --------------------------------------------------------------
    def teardown(self, tags: dict[str, str]) -> list[str]:
        """Delete the scheduled batch, buckets, Artifact Registry repos and models labelled with all of `tags`.

        Deletion is asynchronous on GCP; re-run `make cloud-check`/list and check billing.
        """
        deleted: list[str] = []
        deleted += self._teardown_scheduled_batch(tags)  # stop the clock before emptying the bucket
        client = self._client()
        for bucket in client.list_buckets():
            labels = bucket.labels or {}
            if all(labels.get(k) == v for k, v in tags.items()):
                for blob in bucket.list_blobs():  # objects first; bucket must be empty
                    blob.delete()
                bucket.delete()
                deleted.append(f"gs://{bucket.name}")
                log.info("deleted bucket %s", bucket.name)

        listing = subprocess.run(
            ["gcloud", "artifacts", "repositories", "list",
             f"--project={self.cfg.project_id}", f"--location={self.cfg.region}",
             "--format=json"],
            capture_output=True, text=True, check=True,
        )
        for repo in json.loads(listing.stdout or "[]"):
            labels = repo.get("labels") or {}
            if all(labels.get(k) == v for k, v in tags.items()):
                name = repo["name"]  # projects/<p>/locations/<l>/repositories/<r>
                subprocess.run(
                    ["gcloud", "artifacts", "repositories", "delete", name, "--quiet",
                     f"--project={self.cfg.project_id}"], check=True)
                deleted.append(name)

        try:
            aiplatform = self._aiplatform()
            flt = " AND ".join(f'labels.{k}="{v}"' for k, v in tags.items())
            for model in aiplatform.Model.list(filter=flt):
                model.delete()
                deleted.append(model.resource_name)
        except ImportError:
            log.warning("google-cloud-aiplatform not installed; registry models were not checked")
        return deleted
