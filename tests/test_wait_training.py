"""Waiting for a training job really waits, and a failed job is an error, not a success."""
from __future__ import annotations

import pytest

from cloudlayer.gcp import wait_for_final_state


def _states(*seq):
    it = iter(seq)
    return lambda: next(it)


def test_polls_until_the_job_succeeds():
    slept = []
    state = wait_for_final_state(
        _states(("JOB_STATE_PENDING", ""), ("JOB_STATE_RUNNING", ""), ("JOB_STATE_SUCCEEDED", "")),
        poll_seconds=7, sleep=slept.append)
    assert state == "JOB_STATE_SUCCEEDED" and slept == [7, 7]


def test_a_pending_job_is_not_a_finished_job():
    calls = []

    def fetch():
        calls.append(1)
        return ("JOB_STATE_PENDING", "") if len(calls) < 3 else ("JOB_STATE_SUCCEEDED", "")

    wait_for_final_state(fetch, sleep=lambda _: None)
    assert len(calls) == 3


@pytest.mark.parametrize("state", ["JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"])
def test_unsuccessful_final_states_raise_with_the_jobs_error(state):
    with pytest.raises(RuntimeError, match="out of memory"):
        wait_for_final_state(_states((state, "out of memory")), sleep=lambda _: None)


def test_gives_up_after_the_timeout_but_says_the_job_keeps_running():
    now = iter(range(0, 1000, 10))
    with pytest.raises(TimeoutError, match="keeps running"):
        wait_for_final_state(lambda: ("JOB_STATE_RUNNING", ""), poll_seconds=1, timeout_seconds=25,
                             sleep=lambda _: None, clock=lambda: next(now))
