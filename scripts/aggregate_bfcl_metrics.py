#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


OVERALL_ACC_KEYS = {"acc", "accuracy", "overall_accuracy", "overall_acc", "score"}
OVERALL_COST_KEYS = {"cost", "total_cost", "usd_cost", "request_cost"}
OVERALL_LATENCY_KEYS = {"latency", "latency_ms", "avg_latency_ms", "mean_latency_ms"}
SUBSET_CONTAINER_KEYS = {"subsets", "per_subset", "subset_scores", "category_scores", "metrics_by_subset"}
METRIC_FILE_HINTS = ("metric", "score", "result", "summary", "eval")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def flatten_numeric_metrics(data: Any, prefix: str = "") -> Iterable[Tuple[str, float]]:
    if isinstance(data, dict):
        for key, value in data.items():
            nested = f"{prefix}.{key}" if prefix else str(key)
            yield from flatten_numeric_metrics(value, nested)
    elif isinstance(data, list):
        for index, value in enumerate(data):
            yield from flatten_numeric_metrics(value, f"{prefix}[{index}]")
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        yield prefix, float(data)


def discover_bfcl_metrics(root: Path) -> Tuple[Dict[str, float], Dict[str, float], list[str]]:
    overall: Dict[str, float] = {}
    subsets: Dict[str, float] = {}
    sources: list[str] = []

    candidates = sorted(path for path in root.rglob("*.json") if any(hint in path.name.lower() for hint in METRIC_FILE_HINTS))
    for path in candidates:
        data = load_json(path)
        if data is None:
            continue

        hits = 0
        if isinstance(data, dict):
            for key, value in data.items():
                lowered = str(key).lower()
                if lowered in OVERALL_ACC_KEYS and isinstance(value, (int, float)):
                    overall["acc"] = float(value)
                    hits += 1
                elif lowered in OVERALL_COST_KEYS and isinstance(value, (int, float)):
                    overall["cost"] = float(value)
                    hits += 1
                elif lowered in OVERALL_LATENCY_KEYS and isinstance(value, (int, float)):
                    overall["latency"] = float(value)
                    hits += 1
                elif lowered in SUBSET_CONTAINER_KEYS and isinstance(value, dict):
                    for subset, score in value.items():
                        if isinstance(score, (int, float)):
                            subsets[str(subset)] = float(score)
                            hits += 1

        for key, value in flatten_numeric_metrics(data):
            leaf = key.split(".")[-1]
            if leaf in OVERALL_ACC_KEYS and "acc" not in overall:
                overall["acc"] = value
                hits += 1
            elif leaf in OVERALL_COST_KEYS and "cost" not in overall:
                overall["cost"] = value
                hits += 1
            elif leaf in OVERALL_LATENCY_KEYS and "latency" not in overall:
                overall["latency"] = value
                hits += 1

        if hits:
            sources.append(str(path))

    return overall, subsets, sources


def trace_summary(trace_dir: Path) -> Tuple[list[Dict[str, Any]], Dict[str, Any]]:
    repairs: list[Dict[str, Any]] = []
    repair_kinds: Counter[str] = Counter()
    issue_kinds: Counter[str] = Counter()
    status_codes: Counter[str] = Counter()
    latencies: list[float] = []
    fallback_count = 0
    trace_count = 0

    for path in sorted(trace_dir.glob("*.json")):
        payload = load_json(path)
        if not isinstance(payload, dict):
            continue
        trace_count += 1
        status_codes[str(payload.get("status_code", "unknown"))] += 1
        latency = payload.get("latency_ms")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))

        trace_repairs = payload.get("repairs", [])
        if isinstance(trace_repairs, list):
            for repair in trace_repairs:
                if isinstance(repair, dict):
                    repair_record = {"trace_id": payload.get("trace_id"), **repair}
                    repairs.append(repair_record)
                    repair_kinds[str(repair.get("kind", "unknown"))] += 1

        validation = payload.get("validation", {})
        if isinstance(validation, dict):
            if validation.get("fallback_applied"):
                fallback_count += 1
            for issue in validation.get("issues", []):
                if isinstance(issue, dict):
                    issue_kinds[str(issue.get("kind", "unknown"))] += 1

    summary = {
        "trace_count": trace_count,
        "repair_count": len(repairs),
        "repair_kinds": dict(repair_kinds),
        "validation_issue_count": sum(issue_kinds.values()),
        "validation_issue_kinds": dict(issue_kinds),
        "fallback_count": fallback_count,
        "status_codes": dict(status_codes),
        "mean_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
        "max_latency_ms": round(max(latencies), 3) if latencies else 0.0,
    }
    return repairs, summary


def compute_regression(baseline_path: Path | None, subsets: Dict[str, float]) -> float:
    if baseline_path is None or not baseline_path.exists():
        return 0.0
    baseline = load_json(baseline_path)
    if not isinstance(baseline, dict):
        return 0.0
    baseline_subsets = baseline.get("subsets", {})
    if not isinstance(baseline_subsets, dict):
        return 0.0

    regression = 0.0
    for subset, base_score in baseline_subsets.items():
        candidate_score = subsets.get(str(subset))
        if candidate_score is None:
            continue
        delta = float(base_score) - float(candidate_score)
        if delta > 0:
            regression += delta
    return round(regression, 6)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bfcl-root", required=True)
    parser.add_argument("--trace-dir", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--repairs-out", required=True)
    parser.add_argument("--failure-summary-out", required=True)
    parser.add_argument("--baseline-metrics")
    parser.add_argument("--label", default="")
    parser.add_argument("--protocol-id", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--test-category", default="")
    args = parser.parse_args()

    bfcl_root = Path(args.bfcl_root)
    trace_dir = Path(args.trace_dir)
    out_path = Path(args.out)
    repairs_path = Path(args.repairs_out)
    failure_summary_path = Path(args.failure_summary_out)

    overall, subsets, metric_sources = discover_bfcl_metrics(bfcl_root)
    repairs, failure_summary = trace_summary(trace_dir)
    regression = compute_regression(Path(args.baseline_metrics), subsets) if args.baseline_metrics else 0.0

    metrics = {
        "label": args.label,
        "protocol_id": args.protocol_id,
        "model": args.model,
        "test_category": args.test_category,
        "acc": overall.get("acc", 0.0),
        "cost": overall.get("cost", 0.0),
        "latency": overall.get("latency", failure_summary["mean_latency_ms"]),
        "regression": regression,
        "repair_count": failure_summary["repair_count"],
        "validation_issue_count": failure_summary["validation_issue_count"],
        "fallback_count": failure_summary["fallback_count"],
        "subsets": subsets,
        "metric_sources": metric_sources,
        "bfcl_root": str(bfcl_root),
        "trace_dir": str(trace_dir),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    repairs_path.parent.mkdir(parents=True, exist_ok=True)
    failure_summary_path.parent.mkdir(parents=True, exist_ok=True)

    out_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    failure_summary_path.write_text(json.dumps(failure_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    with repairs_path.open("w", encoding="utf-8") as handle:
        for repair in repairs:
            handle.write(json.dumps(repair, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
