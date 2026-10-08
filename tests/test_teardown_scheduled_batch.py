"""Teardown removes the Cloud Run job and Scheduler entry, tolerates disabled APIs."""
from __future__ import annotations

import json
from types import SimpleNamespace

from cloudlayer import gcp

TAGS = {"course": "itcs355", "student": "proj", "lab": "capstone"}
CFG = SimpleNamespace(project_id="proj", region="asia-southeast1")


def _fake_gcloud(monkeypatch, schedules, jobs, list_ok=True):
    ran: list[list[str]] = []

    def run(cmd, capture_output=False, text=False, check=False):
        ran.append(cmd)
        if "list" in cmd:
            payload = schedules if "scheduler" in cmd else jobs
            return SimpleNamespace(returncode=0 if list_ok else 1,
                                   stdout=json.dumps(payload), stderr="API not enabled")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(gcp.subprocess, "run", run)
    return ran


def test_deletes_matching_schedule_and_labelled_job_only(monkeypatch):
    ran = _fake_gcloud(
        monkeypatch,
        schedules=[{"name": "projects/proj/locations/l/jobs/lemon-batch-every-30min"},
                   {"name": "projects/proj/locations/l/jobs/other-team-job"}],
        jobs=[{"metadata": {"name": "lemon-batch", "labels": TAGS}},
              {"metadata": {"name": "old-lab", "labels": {"course": "itcs355"}}}],
    )
    deleted = gcp.GcpAdapter(CFG)._teardown_scheduled_batch(TAGS)
    assert deleted == ["projects/proj/locations/l/jobs/lemon-batch-every-30min", "run job lemon-batch"]
    deletions = [c for c in ran if "delete" in c]
    assert len(deletions) == 2
    assert all("other-team-job" not in " ".join(c) and "old-lab" not in " ".join(c) for c in deletions)


def test_skips_quietly_when_the_apis_are_not_enabled(monkeypatch):
    ran = _fake_gcloud(monkeypatch, schedules=[], jobs=[], list_ok=False)
    assert gcp.GcpAdapter(CFG)._teardown_scheduled_batch(TAGS) == []
    assert not [c for c in ran if "delete" in c]
