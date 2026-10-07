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
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from cloudlayer.base import CloudAdapter

log = logging.getLogger(__name__)


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

    # --- teardown --------------------------------------------------------------
    def teardown(self, tags: dict[str, str]) -> list[str]:
        """Delete buckets and Artifact Registry repos whose labels include all of `tags`.

        Deletion is asynchronous on GCP; re-run `make cloud-check`/list and check billing.
        """
        deleted: list[str] = []
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
        return deleted
