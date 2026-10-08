"""Scheduled batch inference over a local folder of lemon-leaf photos.

    python -m src.batch.run                # process new files in data/intake
    python -m src.batch.run --reprocess    # replay everything in data/intake

Folder contract (mirrors the object-store prefixes the sync scripts use):

    intake/      photos from growers. Never modified or deleted by this job.
    archive/     copy of every photo that was scored.
    quarantine/  copy of every photo that was rejected or crashed the scorer.
    output/results/<batch_id>.csv     one row per photo
    output/summary/<batch_id>.json    batch-level rates (rejected rate, low confidence rate)
    output/logs/<batch_id>.jsonl      one JSON log line per event

"New" means: present in intake/ and absent from both archive/ and quarantine/.
Nothing new -> exit 0 immediately, without loading the model.

This module talks to the local filesystem only. It holds no cloud credentials and
imports no provider SDK; scripts/sync_down.py and scripts/sync_up.py move files.

Failure contract: one bad file never stops the batch. Every per-file exception is caught,
the file is quarantined, and the batch carries on with the rest.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
HEALTHY_CLASS = "Healthy_Leaf"
LOW_CONFIDENCE = 0.60
REJECTED_SAMPLE_LIMIT = 5      # filenames named in the summary (for alert messages)
HISTOGRAM_BINS = 10          # confidence histogram: 10 bins of width 0.1

CSV_COLUMNS = [
    "batch_id", "filename", "status", "predicted_class", "confidence",
    "needs_inspection", "model_version", "blur_score", "foliage_ratio",
    "rejection_reason", "processed_at",
]


@dataclass
class Components:
    """What the batch needs from the model package. Injected so tests need no torch."""
    validate: Callable            # Path -> (ValidationResult-like, PIL image | None)
    predict: Callable             # PIL image -> (class_name, confidence)
    model_version: str
    manifest: dict = field(default_factory=dict)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_batch_id() -> str:
    return "batch-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class EventLog:
    """JSON-lines log to stdout and to a file, always carrying the batch id."""

    def __init__(self, batch_id: str, path: Path | None) -> None:
        self.batch_id = batch_id
        self.path = path
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: str, **fields) -> None:
        record = {"ts": utc_now(), "batch_id": self.batch_id, "event": event, **fields}
        line = json.dumps(record, ensure_ascii=False)
        print(line, flush=True)
        if self.path is not None:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")


def list_images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)


def find_new_files(intake: Path, archive: Path, quarantine: Path, reprocess: bool) -> list[Path]:
    files = list_images(intake)
    if reprocess:
        return files
    done = {p.name for p in archive.iterdir()} if archive.is_dir() else set()
    done |= {p.name for p in quarantine.iterdir()} if quarantine.is_dir() else set()
    return [p for p in files if p.name not in done]


def _copy(src: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest_dir / src.name)


def _row(batch_id: str, name: str, status: str, **extra) -> dict:
    row = {c: "" for c in CSV_COLUMNS}
    row.update(batch_id=batch_id, filename=name, status=status, processed_at=utc_now())
    row.update({k: v for k, v in extra.items() if v is not None})
    return row


def process_file(path: Path, comp: Components, batch_id: str, archive: Path,
                 quarantine: Path, log: EventLog) -> dict:
    """Score one file. Never raises: any failure becomes a quarantined row."""
    try:
        result, image = comp.validate(path)
        if not result.is_valid:
            _copy(path, quarantine)
            log.emit("file_rejected", filename=path.name, status=result.status,
                     reason=result.rejection_reason)
            return _row(batch_id, path.name, result.status,
                        model_version=comp.model_version,
                        blur_score=_r(result.blur_score), foliage_ratio=_r(result.foliage_ratio),
                        rejection_reason=result.rejection_reason)

        cls, conf = comp.predict(image)
        _copy(path, archive)
        # Contract (docs/DATA_CONTRACT.md): not Healthy, OR too unsure to trust a 'Healthy'.
        needs = cls != HEALTHY_CLASS or conf < LOW_CONFIDENCE
        log.emit("file_scored", filename=path.name, predicted_class=cls,
                 confidence=round(conf, 4), needs_inspection=needs)
        return _row(batch_id, path.name, "SCORED", predicted_class=cls,
                    confidence=round(conf, 4), needs_inspection=str(needs).lower(),
                    model_version=comp.model_version,
                    blur_score=_r(result.blur_score), foliage_ratio=_r(result.foliage_ratio))
    except Exception as exc:  # noqa: BLE001 - this is the safety net by design
        reason = f"{type(exc).__name__}: {exc}"
        try:
            _copy(path, quarantine)
        except Exception as copy_exc:  # noqa: BLE001
            reason += f" (quarantine copy also failed: {copy_exc})"
        log.emit("file_error", filename=path.name, status="ERROR_UNEXPECTED", reason=reason)
        return _row(batch_id, path.name, "ERROR_UNEXPECTED",
                    model_version=comp.model_version, rejection_reason=reason)


def _r(value) -> float | None:
    return None if value is None else round(float(value), 3)


def confidence_histogram(confidences: list[float]) -> dict[str, int]:
    """Counts per 0.1-wide bin, always all bins present; 1.0 falls in the last bin."""
    width = 1 / HISTOGRAM_BINS
    keys = [f"{i * width:.1f}-{(i + 1) * width:.1f}" for i in range(HISTOGRAM_BINS)]
    hist = dict.fromkeys(keys, 0)
    for c in confidences:
        hist[keys[min(int(c * HISTOGRAM_BINS), HISTOGRAM_BINS - 1)]] += 1
    return hist


def summarise(rows: list[dict], batch_id: str, model_version: str, duration_s: float) -> dict:
    total = len(rows)
    scored = [r for r in rows if r["status"] == "SCORED"]
    rejected = total - len(scored)
    low = [r for r in scored if float(r["confidence"]) < LOW_CONFIDENCE]
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {
        "batch_id": batch_id,
        "finished_at": utc_now(),
        "model_version": model_version,
        "files_total": total,
        "files_scored": len(scored),
        "files_rejected": rejected,
        "rejected_rate": round(rejected / total, 4) if total else 0.0,
        "low_confidence_threshold": LOW_CONFIDENCE,
        "low_confidence_count": len(low),
        # Denominator is scored files: a rejected file has no confidence to be low.
        "low_confidence_rate": round(len(low) / len(scored), 4) if scored else 0.0,
        "needs_inspection_count": sum(1 for r in scored if r["needs_inspection"] == "true"),
        "by_status": by_status,
        # Up to REJECTED_SAMPLE_LIMIT rejected files (sorted by name): examples for an alert.
        "rejected_samples": [{"filename": r["filename"], "status": r["status"]}
                             for r in sorted((r for r in rows if r["status"] != "SCORED"),
                                             key=lambda r: r["filename"])[:REJECTED_SAMPLE_LIMIT]],
        "confidence_histogram": confidence_histogram([float(r["confidence"]) for r in scored]),
        "duration_seconds": round(duration_s, 2),
    }


def run_batch(intake: Path, archive: Path, quarantine: Path, output: Path,
              load_components: Callable[[], Components], batch_id: str | None = None,
              reprocess: bool = False) -> dict | None:
    """Returns the summary dict, or None when there was nothing new to do."""
    batch_id = batch_id or new_batch_id()
    log = EventLog(batch_id, output / "logs" / f"{batch_id}.jsonl")
    started = time.monotonic()

    new_files = find_new_files(intake, archive, quarantine, reprocess)
    if not new_files:
        log.emit("batch_skipped", reason="no new files")
        # No log file for a skipped run: it would upload an empty batch every 30 minutes.
        try:
            (output / "logs" / f"{batch_id}.jsonl").unlink()
        except FileNotFoundError:
            pass
        return None

    log.emit("batch_started", files=len(new_files), reprocess=reprocess)
    comp = load_components()          # model loads once, only when there is work
    log.emit("model_loaded", model_version=comp.model_version)

    rows = [process_file(p, comp, batch_id, archive, quarantine, log) for p in new_files]

    results_path = output / "results" / f"{batch_id}.csv"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    summary = summarise(rows, batch_id, comp.model_version, time.monotonic() - started)
    summary_path = output / "summary" / f"{batch_id}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.emit("batch_finished", **{k: v for k, v in summary.items()
                                  if k not in ("batch_id", "by_status", "rejected_samples",
                                               "confidence_histogram")})
    return summary


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() not in ("0", "false", "no", "off", "")


def default_components(model_dir: Path) -> Components:
    """Real model + real validator. Heavy imports live here so tests can avoid them."""
    from src.model.inference import load_model, predict
    from src.model.validator import InputValidator

    model, classes, manifest = load_model(model_dir)
    validator = InputValidator(
        blur_threshold=float(os.environ.get("BLUR_THRESHOLD", "65.0")),
        foliage_threshold=float(os.environ.get("FOLIAGE_THRESHOLD", "0.05")),
        # The deliberate-failure demo turns OOD screening off to show that confidence
        # alone does not catch non-leaf photos.
        enable_blur_check=_env_flag("ENABLE_BLUR_CHECK", True),
        enable_ood_check=_env_flag("ENABLE_OOD_CHECK", True),
    )
    return Components(
        validate=validator.validate_file,
        predict=lambda img: predict(img, model, classes),
        model_version=str(manifest.get("version", "unknown")),
        manifest=manifest,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    data = Path(os.environ.get("DATA_DIR", "data"))
    p.add_argument("--intake", type=Path, default=data / "intake")
    p.add_argument("--archive", type=Path, default=data / "archive")
    p.add_argument("--quarantine", type=Path, default=data / "quarantine")
    p.add_argument("--output", type=Path, default=data / "output")
    p.add_argument("--model-dir", type=Path,
                   default=Path(os.environ.get("MODEL_DIR", "models/registry/lemon_classifier_v2")))
    p.add_argument("--batch-id", default=os.environ.get("BATCH_ID"))
    p.add_argument("--reprocess", action="store_true",
                   help="ignore archive/quarantine and score everything in intake again")
    args = p.parse_args(argv)

    try:
        run_batch(args.intake, args.archive, args.quarantine, args.output,
                            lambda: default_components(args.model_dir),
                            batch_id=args.batch_id, reprocess=args.reprocess)
    except Exception as exc:  # noqa: BLE001 - model missing etc.: fail loudly, non-zero
        print(json.dumps({"ts": utc_now(), "event": "batch_failed",
                          "reason": f"{type(exc).__name__}: {exc}"}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
