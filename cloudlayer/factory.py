"""Adapter selection. The only place that maps CLOUD_PROVIDER to an implementation.

This project implements one provider (GCP). The other providers are deliberately absent:
the course asks for exactly one real adapter, and dead stubs only hide what actually runs.
"""
from __future__ import annotations

from cloudlayer.base import CloudAdapter, LocalAdapter


def get_adapter(cfg) -> CloudAdapter:
    provider = (cfg.provider or "local").lower()
    if provider == "local":
        return LocalAdapter(cfg)
    if provider == "gcp":
        from cloudlayer.gcp import GcpAdapter

        return GcpAdapter(cfg)
    raise ValueError(
        f"Unsupported CLOUD_PROVIDER={provider!r}. This project implements gcp (and local for tests)."
    )
