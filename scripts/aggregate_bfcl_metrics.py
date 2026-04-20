#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


OVERALL_ACC_KEYS = {"acc", "accuracy", "overall_accuracy", "overall_acc", "score"}
OVERALL_COST_KEYS = {"cost", "total_cost", "usd_cost", "request_cost"}
OVERALL_LATENCY_KEYS = {"latency", "latency_ms", "avg_latency_ms", "mean_latency_ms"}
SUBSET_CONTAINER_KEYS = {"subsets", "per_subset", "subset_scores", "category_scores", "metrics_by_subset"}
METRIC_FILE_HINTS = ("metric", "score", "result", "summary", "eval")
CSV_METRIC_SUFFIXES = {".csv", ".tsv"}
NON_METRIC_HEADERS = {"rank", "model", "model link", "organization", "license"}
OVERALL_CSV_ACC_HEADERS = {"overall acc", "overall accuracy", "overall score"}
OVERALL_CSV_COST_HEADERS = {"total cost", "total cost $", "cost", "request cost"}
OVERALL_CSV_LATENCY_HEADERS = {"latency mean", "latency mean s", "latency", "latency s"}
OVERALL_CSV_SKIP_HEADERS = NON_METRIC_HEADERS | {
    "latency standard deviation",
    "latency standard deviation s",
    "latency 95th percentile",
    "latency 95th percentile s",
}
CSV_CONTEXT_PREFIXES = {
    "data_non_live": "non_live",
    "data_multi_turn": "multi_turn",
    "data_live": "live",
    "data_web_search": "web_search",
    "data_memory": "memory",
    "data_format_sensitivity": "format_sensitivity",
    "data_agentic": "agentic",
}

CATEGORY_TO_SUBSET_PATTERNS = {
    "simple_python": ["simple", "python_simple", "non_live_python_simple_ast", "non_live", "live", "ast", "python"],
    "multiple": ["multiple", "parallel_multiple", "parallel"],
    "parallel_multiple": ["parallel", "multiple"],
    "multi_turn_miss_param": ["multi_turn", "miss_param", "multi", "turn", "miss"],
}


def _metric_source_priority(path: Path) -> tuple[int, str]:
    path_str = str(path).lower()
    if path.suffix.lower() in CSV_METRIC_SUFFIXES:
        if "data_overall" in path_str:
            return (0, path_str)
        return (1, path_str)
    if "summary" in path_str or "metric" in path_str:
        return (2, path_str)
    return (3, path_str)


def load_json(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except Exception:
        pass

    decoder = json.JSONDecoder()
    idx = 0
    values = []
    n = len(text)
    while idx < n:
        while idx < n and text[idx].isspace():
            idx += 1
        if idx >= n:
            break
        try:
            value, next_idx = decoder.raw_decode(text, idx)
        except Exception:
            break
        values.append(value)
        idx = next_idx
    if values:
        return values
    return None


def _normalize_label(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _parse_numeric_token(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None

    stripped = value.strip()
    if not stripped or stripped.lower() in {"n/a", "na", "none", "null", "-"}:
        return None

    token = stripped[:-1] if stripped.endswith("%") else stripped
    token = token.replace(",", "").strip()
    try:
        return float(token)
    except ValueError:
        return None


def _csv_context_prefix(path: Path) -> str | None:
    stem = path.stem.lower()
    for marker, prefix in CSV_CONTEXT_PREFIXES.items():
        if marker in stem:
            return prefix
    return None


def _canonical_subset_key(header: str, context_prefix: str | None = None) -> str | None:
    normalized = _normalize_label(header)
    if not normalized or normalized in NON_METRIC_HEADERS:
        return None

    if context_prefix is None:
        if normalized in OVERALL_CSV_SKIP_HEADERS:
            return None
        if normalized in OVERALL_CSV_ACC_HEADERS | OVERALL_CSV_COST_HEADERS | OVERALL_CSV_LATENCY_HEADERS:
            return None
        key = normalized
    else:
        context_words = context_prefix.replace("_", " ")
        if normalized.startswith(f"{context_words} "):
            key = normalized
        elif normalized == "overall acc":
            key = f"{context_words} overall acc"
        else:
            key = f"{context_words} {normalized}"
    return key.replace(" ", "_")


def _extract_subset_metrics_from_summary(data: Dict[str, Any]) -> Dict[str, float]:
    subsets: Dict[str, float] = {}
    for key, value in data.items():
        normalized = _normalize_label(str(key))
        if not isinstance(value, (int, float)) or normalized in OVERALL_ACC_KEYS | OVERALL_COST_KEYS | OVERALL_LATENCY_KEYS:
            continue
        subset_key = _canonical_subset_key(str(key))
        if subset_key:
            subsets[subset_key] = float(value)
    return subsets


def _discover_from_object(data: Any) -> Tuple[Dict[str, float], Dict[str, float], int]:
    overall: Dict[str, float] = {}
    subsets: Dict[str, float] = {}
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
        summary_subsets = _extract_subset_metrics_from_summary(data)
        if summary_subsets:
            subsets.update(summary_subsets)
            hits += len(summary_subsets)

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
    return overall, subsets, hits


def _discover_from_csv(path: Path) -> Tuple[Dict[str, float], Dict[str, float], int]:
    overall: Dict[str, float] = {}
    subsets: Dict[str, float] = {}
    hits = 0
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","

    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            rows = [row for row in reader if row and any(str(value).strip() for value in row.values())]
    except Exception:
        return overall, subsets, hits

    if not rows:
        return overall, subsets, hits

    row = max(
        rows,
        key=lambda item: sum(
            1 for value in item.values() if isinstance(value, str) and value.strip() and value.strip().lower() not in {"n/a", "na"}
        ),
    )
    context_prefix = _csv_context_prefix(path)

    for header, raw_value in row.items():
        number = _parse_numeric_token(raw_value)
        if number is None:
            continue
        normalized = _normalize_label(header)

        if context_prefix is None:
            if normalized in OVERALL_CSV_ACC_HEADERS:
                overall["acc"] = number
                hits += 1
                continue
            if normalized in OVERALL_CSV_COST_HEADERS:
                overall["cost"] = number
                hits += 1
                continue
            if normalized in OVERALL_CSV_LATENCY_HEADERS:
                overall["latency"] = number * 1000.0
                hits += 1
                continue

        subset_key = _canonical_subset_key(header, context_prefix)
        if subset_key:
            subsets[subset_key] = number
            hits += 1

    return overall, subsets, hits


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

    candidates = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".json", *CSV_METRIC_SUFFIXES}
            and any(hint in str(path).lower() for hint in METRIC_FILE_HINTS)
        ),
        key=_metric_source_priority,
    )
    for path in candidates:
        hits = 0
        if path.suffix.lower() in CSV_METRIC_SUFFIXES:
            discovered_overall, discovered_subsets, hits = _discover_from_csv(path)
            for key, value in discovered_overall.items():
                overall.setdefault(key, value)
            subsets.update(discovered_subsets)
        else:
            data = load_json(path)
            if data is None:
                continue
            objects = data if isinstance(data, list) else [data]
            for obj in objects:
                discovered_overall, discovered_subsets, obj_hits = _discover_from_object(obj)
                hits += obj_hits
                for key, value in discovered_overall.items():
                    overall.setdefault(key, value)
                subsets.update(discovered_subsets)

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


def _canonical_test_category_key(test_category: str) -> str:
    return _normalize_label(test_category).replace(" ", "_")


def _resolve_score_sources(metric_sources: list[str]) -> list[str]:
    resolved = []
    for source in metric_sources:
        low = source.lower()
        if "/score/" in low or "data_" in low or source.endswith((".csv", ".tsv")):
            resolved.append(source)
    return resolved


def _resolve_result_json_paths(bfcl_root: Path) -> list[str]:
    result_dir = bfcl_root / "result"
    if not result_dir.exists():
        return []
    return [str(path) for path in sorted(result_dir.rglob("*.json")) if path.is_file()]


def _assess_evaluation_status(
    *,
    overall: Dict[str, float],
    subsets: Dict[str, float],
    metric_sources: list[str],
    failure_summary: Dict[str, Any],
    bfcl_root: Path,
    test_category: str,
) -> tuple[str, list[str], list[str], list[str]]:
    issues: list[str] = []
    category_key = _canonical_test_category_key(test_category)
    resolved_score_sources = _resolve_score_sources(metric_sources)
    result_json_paths = _resolve_result_json_paths(bfcl_root)

    if "acc" not in overall and overall.get("accuracy") is None:
        issues.append("overall acc missing")

    # Semi-structured subset validation (user-preferred approach for BFCL outputs)
    # Handles real keys like 'non_live_python_simple_ast', 'non_live_overall_acc',
    # 'live_acc', 'correct_count', 'total_count' etc. instead of exact test_category match.
    relevant_patterns = CATEGORY_TO_SUBSET_PATTERNS.get(
        test_category.lower().replace("_", ""), [category_key]
    )
    has_relevant_subset = any(
        any(
            p.lower() in k.lower() or k.lower() in p.lower()
            for p in relevant_patterns
        )
        for k in subsets.keys()
    )

    if category_key and not has_relevant_subset:
        issues.append(
            f"subset metric missing for test_category={category_key} "
            f"(looked for patterns: {relevant_patterns})"
        )
    if not result_json_paths:
        issues.append("no result json found")
    if not resolved_score_sources:
        issues.append("no score source resolved")
    if not metric_sources:
        issues.append("metric_sources empty")
    trace_count = failure_summary.get("trace_count")
    if not isinstance(trace_count, (int, float)) or float(trace_count) <= 0:
        issues.append("trace summary invalid: trace_count <= 0")

    status = "complete" if not issues else "incomplete"
    return status, issues, resolved_score_sources, result_json_paths


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
    latency = overall.get("latency", failure_summary["mean_latency_ms"])
    if latency and latency < 100 and failure_summary["mean_latency_ms"] >= 100:
        latency *= 1000.0

    evaluation_status, artifact_issues, resolved_score_sources, result_json_paths = _assess_evaluation_status(
        overall=overall,
        subsets=subsets,
        metric_sources=metric_sources,
        failure_summary=failure_summary,
        bfcl_root=bfcl_root,
        test_category=args.test_category,
    )

    metrics = {
        "label": args.label,
        "protocol_id": args.protocol_id,
        "model": args.model,
        "test_category": args.test_category,
        "acc": overall.get("acc"),
        "cost": overall.get("cost", 0.0),
        "latency": latency,
        "regression": regression,
        "repair_count": failure_summary["repair_count"],
        "validation_issue_count": failure_summary["validation_issue_count"],
        "fallback_count": failure_summary["fallback_count"],
        "subsets": subsets,
        "metric_sources": metric_sources,
        "resolved_score_sources": resolved_score_sources,
        "result_json_paths": result_json_paths,
        "evaluation_status": evaluation_status,
        "artifact_validity_issues": artifact_issues,
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
