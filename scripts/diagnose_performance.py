"""Diagnose WHY batch quality dropped: compare recent batches with earlier ones.

    python scripts/diagnose_performance.py                      # data/output/results/*.csv
    python scripts/diagnose_performance.py --from-cloud         # results/*.csv from object storage
    python scripts/diagnose_performance.py --recent-batches 3   # last 3 batches vs everything earlier
    python scripts/diagnose_performance.py --since 2026-10-11T00:00:00Z

Why this exists. The alerts say THAT something moved (rejected rate, low-confidence rate). This
script asks the next question, "what moved, and is it the photos or the model?", the way the
monitoring lab does: split the signals, compare a baseline window with a recent window, and map
the pattern of changes to a likely cause.

It cannot measure accuracy. Production photos have no labels, so it works from proxies that the
batch already writes (status, confidence, predicted class, blur score, foliage ratio). A "cause"
is a lead for a human to check, not a proof.

Standard library only, so it runs anywhere the CSVs are. Reads the CSV files that
`src/batch/run.py` writes (one row per photo).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.batch.run import HEALTHY_CLASS, HISTOGRAM_BINS, LOW_CONFIDENCE

DEFAULT_RESULTS = ROOT / "data" / "output" / "results"

MIN_SAMPLES = 30          # scored photos per window before a distribution test means anything
RATE_RISE = 0.10          # a rate that rises by this much (10 points) is flagged
LOW_CONF_ALERT = 0.30     # same level as the low-confidence alert policy
PSI_MODERATE = 0.10       # conventional population-stability-index bands
PSI_MAJOR = 0.25
KS_C_ALPHA = 1.358        # two-sample Kolmogorov-Smirnov critical constant at alpha = 0.05
EPS = 1e-4

REJECT_CAUSES = {
    "REJECTED_BLURRED": "Image quality: more blurred photos are arriving (check camera focus, motion, compression).",
    "REJECTED_OOD_NON_LEAF": "Out-of-domain inputs: photos that are not lemon leaves are arriving.",
    "REJECTED_RESOLUTION": "Upload problem: photos are too small (resized or thumbnail uploads).",
    "REJECTED_CORRUPTED": "Upload problem: files are corrupted or truncated (transfer or storage fault).",
    "ERROR_UNEXPECTED": "Pipeline problem: unexpected errors while scoring (read the file_error log lines).",
}


# --- loading ---------------------------------------------------------------------------------

def _num(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def load_rows(paths: list[Path]) -> list[dict]:
    """Rows from batch result CSVs, in batch order. Unreadable files are skipped, not fatal."""
    rows: list[dict] = []
    for path in sorted(paths):
        try:
            with open(path, newline="", encoding="utf-8") as fh:
                rows.extend(csv.DictReader(fh))
        except (OSError, UnicodeDecodeError, csv.Error) as exc:
            print(f"skipped {path.name}: {exc}", file=sys.stderr)
    return rows


def split_windows(rows: list[dict], recent_batches: int,
                  since: str | None) -> tuple[list[dict], list[dict], list[str]]:
    """(baseline rows, recent rows, recent batch ids). Batch ids sort by time."""
    batch_ids = sorted({r["batch_id"] for r in rows})
    if since:
        recent_ids = [b for b in batch_ids
                      if min(r["processed_at"] for r in rows if r["batch_id"] == b) >= since]
    else:
        recent_ids = batch_ids[-recent_batches:] if recent_batches > 0 else []
    recent = [r for r in rows if r["batch_id"] in recent_ids]
    baseline = [r for r in rows if r["batch_id"] not in recent_ids]
    return baseline, recent, recent_ids


# --- statistics (no numpy) -------------------------------------------------------------------

def psi(expected: dict, actual: dict) -> float:
    """Population Stability Index between two count dicts over the union of keys.
    < 0.10 stable, 0.10-0.25 moderate shift, > 0.25 major shift."""
    keys = set(expected) | set(actual)
    e_total, a_total = sum(expected.values()), sum(actual.values())
    if not keys or e_total == 0 or a_total == 0:
        return 0.0
    total = 0.0
    for k in keys:
        e = max(expected.get(k, 0) / e_total, EPS)
        a = max(actual.get(k, 0) / a_total, EPS)
        total += (a - e) * math.log(a / e)
    return total


def ks_statistic(a: list[float], b: list[float]) -> float:
    """Largest gap between the two empirical distribution functions."""
    if not a or not b:
        return 0.0
    xs, ys = sorted(a), sorted(b)
    i = j = 0
    d = 0.0
    while i < len(xs) and j < len(ys):
        v = min(xs[i], ys[j])
        while i < len(xs) and xs[i] <= v:
            i += 1
        while j < len(ys) and ys[j] <= v:
            j += 1
        d = max(d, abs(i / len(xs) - j / len(ys)))
    return d


def ks_critical(n: int, m: int) -> float:
    return KS_C_ALPHA * math.sqrt((n + m) / (n * m)) if n and m else float("inf")


def median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


def confidence_bins(values: list[float]) -> dict[str, int]:
    width = 1 / HISTOGRAM_BINS
    counts: dict[str, int] = {f"{i * width:.1f}": 0 for i in range(HISTOGRAM_BINS)}
    for v in values:
        counts[f"{min(int(v * HISTOGRAM_BINS), HISTOGRAM_BINS - 1) * width:.1f}"] += 1
    return counts


# --- one window ------------------------------------------------------------------------------

def summarise(rows: list[dict]) -> dict:
    scored = [r for r in rows if r.get("status") == "SCORED"]
    rejected = [r for r in rows if r.get("status") != "SCORED"]
    conf = [c for c in (_num(r.get("confidence")) for r in scored) if c is not None]
    low = [c for c in conf if c < LOW_CONFIDENCE]
    needs = [r for r in scored if str(r.get("needs_inspection", "")).lower() == "true"]
    return {
        "files": len(rows),
        "scored": len(scored),
        "rejected": len(rejected),
        "rejected_rate": len(rejected) / len(rows) if rows else 0.0,
        "reject_status": dict(Counter(r["status"] for r in rejected)),
        "low_confidence_rate": len(low) / len(conf) if conf else 0.0,
        "mean_confidence": sum(conf) / len(conf) if conf else None,
        "needs_inspection_rate": len(needs) / len(scored) if scored else 0.0,
        "classes": dict(Counter(r["predicted_class"] for r in scored if r.get("predicted_class"))),
        "confidences": conf,
        # blur and foliage are measured for every photo that opened, rejected ones included
        "blur": [v for v in (_num(r.get("blur_score")) for r in rows) if v is not None],
        "foliage": [v for v in (_num(r.get("foliage_ratio")) for r in rows) if v is not None],
    }


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}%"


def _num_s(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.3f}"


def _band(value: float) -> str:
    return "major" if value >= PSI_MAJOR else "moderate" if value >= PSI_MODERATE else "stable"


# --- comparison and diagnosis ----------------------------------------------------------------

def diagnose(baseline_rows: list[dict], recent_rows: list[dict], min_samples: int = MIN_SAMPLES) -> dict:
    base, rec = summarise(baseline_rows), summarise(recent_rows)
    findings: list[dict] = []
    causes: list[str] = []
    notes: list[str] = []

    if not recent_rows:
        return {"baseline": _public(base), "recent": _public(rec), "findings": [], "causes": [],
                "notes": ["No recent batches to examine."], "drift": False, "tested": False}
    if not baseline_rows:
        notes.append("No baseline: at least two batches are needed to compare. Showing the recent window only.")

    def add(name, base_v, rec_v, flagged, detail=""):
        findings.append({"signal": name, "baseline": base_v, "recent": rec_v,
                         "flagged": bool(flagged), "detail": detail})

    have_baseline = bool(baseline_rows)
    enough = base["scored"] >= min_samples and rec["scored"] >= min_samples
    if have_baseline and not enough:
        notes.append(f"Distribution tests skipped: need at least {min_samples} scored photos in each "
                     f"window (baseline {base['scored']}, recent {rec['scored']}). Rates are shown, "
                     "but small samples move a lot; treat them as hints.")

    # 1. rejection rate and its mix: is it the photos?
    rej_up = have_baseline and rec["rejected_rate"] - base["rejected_rate"] >= RATE_RISE
    add("rejected rate", base["rejected_rate"], rec["rejected_rate"], rej_up)
    if rej_up and rec["reject_status"]:
        top, count = max(rec["reject_status"].items(), key=lambda kv: kv[1])
        findings[-1]["detail"] = f"mostly {top} ({count} of {rec['rejected']} rejected)"
        causes.append(REJECT_CAUSES.get(top, f"Rejections are dominated by {top}."))

    # 2. confidence: is it the model?
    low_up = have_baseline and (rec["low_confidence_rate"] - base["low_confidence_rate"] >= RATE_RISE
                                or rec["low_confidence_rate"] >= LOW_CONF_ALERT
                                > base["low_confidence_rate"])
    add("low-confidence rate", base["low_confidence_rate"], rec["low_confidence_rate"], low_up,
        f"threshold {LOW_CONFIDENCE:.2f}")
    mean_down = (have_baseline and None not in (base["mean_confidence"], rec["mean_confidence"])
                 and base["mean_confidence"] - rec["mean_confidence"] >= 0.10)
    add("mean confidence", base["mean_confidence"], rec["mean_confidence"], mean_down)

    conf_shift = class_shift = input_shift = False
    if have_baseline and enough:
        p = psi(confidence_bins(base["confidences"]), confidence_bins(rec["confidences"]))
        conf_shift = p >= PSI_MODERATE
        add("confidence distribution (PSI)", None, p, conf_shift, _band(p))
        p = psi(base["classes"], rec["classes"])
        class_shift = p >= PSI_MODERATE
        add("predicted-class mix (PSI)", None, p, class_shift, _band(p))
        for label, key in (("blur score", "blur"), ("foliage ratio", "foliage")):
            n, m = len(base[key]), len(rec[key])
            d = ks_statistic(base[key], rec[key])
            shifted = n > 0 and m > 0 and d > ks_critical(n, m)
            input_shift = input_shift or shifted
            add(f"{label} (KS)", median(base[key]), median(rec[key]), shifted,
                f"D={d:.3f}, critical {ks_critical(n, m):.3f}; baseline/recent show medians")

    # 3. map the pattern to a cause
    confidence_down = low_up or mean_down or conf_shift
    if input_shift:
        causes.append("Covariate drift: the photos themselves look different (lighting, camera, "
                      "background or season). Compare recent and earlier photos side by side.")
    if confidence_down and not input_shift and not rej_up:
        causes.append("Model uncertainty on in-domain photos with unchanged image statistics: possible "
                      "concept drift (a disease or leaf condition the model did not see). Have a person "
                      "review the needs_inspection files and label a sample.")
    if class_shift and not confidence_down:
        causes.append("Population shift: the mix of predicted diseases changed while confidence held. "
                      "This may be real (an outbreak, a new grower) rather than a model fault.")
    elif class_shift:
        causes.append("The mix of predicted diseases also changed; check whether the new mix matches "
                      "what the growers are sending.")

    drift = any(f["flagged"] for f in findings)
    if have_baseline and not drift and not notes:
        causes.append("No evidence of drift in the available signals.")
    if rec["classes"] and rec["classes"].get(HEALTHY_CLASS, 0) == rec["scored"] and rec["scored"] >= min_samples:
        notes.append("Every scored photo was predicted Healthy: confirm this is plausible; a model that "
                     "always answers Healthy would look perfect on these signals.")

    notes.append("No labels exist in production, so accuracy itself is not measured; these signals are proxies.")
    return {"baseline": _public(base), "recent": _public(rec), "findings": findings,
            "causes": causes, "notes": notes, "drift": drift, "tested": have_baseline and enough}


def _public(summary: dict) -> dict:
    """Window summary without the raw sample lists (kept out of reports and JSON)."""
    return {k: v for k, v in summary.items() if k not in ("confidences", "blur", "foliage")}


# --- report ----------------------------------------------------------------------------------

def _cell(name: str, value) -> str:
    if value is None:
        return "-"
    if "rate" in name:
        return _pct(value)
    return _num_s(value)


def render(result: dict, recent_ids: list[str]) -> str:
    b, r = result["baseline"], result["recent"]
    out = ["# Performance diagnosis", ""]
    out.append(f"Recent window: {len(recent_ids)} batch(es) {', '.join(recent_ids) or '-'}")
    out.append(f"Baseline: {b['files']} photos ({b['scored']} scored); recent: {r['files']} photos "
               f"({r['scored']} scored)")
    out += ["", "| Signal | Baseline | Recent | Flag | Detail |", "|---|---:|---:|:--:|---|"]
    for f in result["findings"]:
        out.append(f"| {f['signal']} | {_cell(f['signal'], f['baseline'])} | "
                   f"{_cell(f['signal'], f['recent'])} | {'FLAG' if f['flagged'] else 'ok'} | {f['detail']} |")
    out += ["", "## Likely causes"]
    out += [f"- {c}" for c in result["causes"]] or ["- None identified from these signals."]
    out += ["", "## Notes"] + [f"- {n}" for n in result["notes"]]
    return "\n".join(out) + "\n"


# --- cloud input -----------------------------------------------------------------------------

def fetch_from_cloud(dest: Path) -> list[Path]:
    """Download results/*.csv through the provider-neutral adapter."""
    from cloudlayer.factory import get_adapter
    from src import config

    adapter = get_adapter(config.load(strict=False))
    paths = []
    for key in adapter.list_keys("results/"):
        name = PurePosixPath(key).name
        if name.endswith(".csv"):
            adapter.download(adapter.uri_for(key), str(dest / name))
            paths.append(dest / name)
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    ap.add_argument("--from-cloud", action="store_true", help="read results/ from object storage")
    ap.add_argument("--recent-batches", type=int, default=3, help="size of the recent window (default 3)")
    ap.add_argument("--since", help="recent window = batches that started at or after this UTC time")
    ap.add_argument("--min-samples", type=int, default=MIN_SAMPLES)
    ap.add_argument("--json", action="store_true", help="print JSON instead of the text report")
    ap.add_argument("--fail-on-drift", action="store_true", help="exit 1 when any signal is flagged")
    args = ap.parse_args(argv)

    if args.from_cloud:
        with tempfile.TemporaryDirectory() as tmp:
            paths = fetch_from_cloud(Path(tmp))
            rows = load_rows(paths)
    else:
        rows = load_rows(sorted(args.results_dir.glob("*.csv")))
    if not rows:
        print("No result rows found. Run a batch first (make run-batch) or use --from-cloud.",
              file=sys.stderr)
        return 2

    baseline, recent, recent_ids = split_windows(rows, args.recent_batches, args.since)
    result = diagnose(baseline, recent, args.min_samples)
    print(json.dumps(result, indent=2) if args.json else render(result, recent_ids))
    return 1 if args.fail_on_drift and result["drift"] else 0


if __name__ == "__main__":
    sys.exit(main())
