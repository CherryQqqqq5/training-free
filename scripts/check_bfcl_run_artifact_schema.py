#!/usr/bin/env python3
"""Validate compact BFCL run artifacts for performance acceptance.

The formal performance path commits only compact evidence. Raw BFCL score/result
trees and traces stay outside the delivery package; this checker therefore
requires summarized source/trace evidence plus candidate-rule provenance for
candidate runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_MANIFEST_FIELDS = (
    "artifact_schema_version",
    "protocol_id",
    "bfcl_model_alias",
    "upstream_profile",
    "upstream_model_route",
    "test_category",
    "runtime_config_path",
    "rules_dir",
    "run_id",
    "kind",
    "comparison_line",
    "selected_case_count",
    "selected_case_ids_hash",
    "provider_preflight_status_path",
    "provider_preflight_passed",
)
REQUIRED_CANDIDATE_RECORD_FIELDS = (
    "case_id",
    "category",
    "candidate_generatable",
    "candidate_origin",
    "rule_type",
    "candidate_rules_type",
    "source_run_root",
    "retention_prior",
    "schema_arg_name",
    "tool",
)


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _first_existing(root: Path, names: tuple[str, ...]) -> Path:
    for name in names:
        path = root / name
        if path.exists():
            return path
    return root / names[0]


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive_count(summary: dict[str, Any], key: str) -> bool:
    value = _number(summary.get(key))
    return value is not None and value > 0


def _sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_path(raw: Any, run_root: Path) -> Path | None:
    if raw in (None, ""):
        return None
    path = Path(str(raw))
    if path.is_absolute():
        return path
    direct = run_root / path
    if direct.exists():
        return direct
    return path


def _load_jsonl(path: Path | None) -> tuple[list[dict[str, Any]], str | None]:
    if path is None:
        return [], "candidate_record_manifest_path_missing"
    if not path.exists():
        return [], "candidate_record_manifest_missing"
    records: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                records.append(item)
            else:
                return [], "candidate_record_manifest_invalid"
    except Exception:
        return [], "candidate_record_manifest_invalid"
    return records, None


def _candidate_record_status(path: Path | None) -> dict[str, Any]:
    records, error = _load_jsonl(path)
    missing_by_index: list[dict[str, Any]] = []
    for idx, record in enumerate(records):
        missing = [field for field in REQUIRED_CANDIDATE_RECORD_FIELDS if record.get(field) in (None, "")]
        retention = record.get("retention_prior")
        if not isinstance(retention, dict):
            missing.append("retention_prior")
        elif retention.get("retain_eligibility") in (None, ""):
            missing.append("retention_prior.retain_eligibility")
        if missing:
            missing_by_index.append({"index": idx, "missing": sorted(set(missing))})
    return {
        "path": str(path) if path else None,
        "present": bool(path and path.exists()),
        "record_count": len(records),
        "required_fields": list(REQUIRED_CANDIDATE_RECORD_FIELDS),
        "missing_fields_by_record": missing_by_index,
        "passed": error is None and bool(records) and not missing_by_index,
        "error": error,
    }


def evaluate(run_root: Path) -> dict[str, Any]:
    manifest_path = _first_existing(run_root, ("run_manifest.json", "artifacts/run_manifest.json"))
    metrics_path = _first_existing(run_root, ("metrics.json", "artifacts/metrics.json"))
    preflight_path = _first_existing(run_root, ("preflight_report.json", "artifacts/preflight_report.json"))
    sanitized_trace_path = _first_existing(run_root, ("sanitized_trace_summary.json", "artifacts/sanitized_trace_summary.json", "sanitized_summary.json", "artifacts/sanitized_summary.json"))
    manifest = _load_json(manifest_path, {}) or {}
    metrics = _load_json(metrics_path, {}) or {}
    preflight = _load_json(preflight_path, {}) or {}
    sanitized_trace_summary = metrics.get("sanitized_trace_summary")
    if not isinstance(sanitized_trace_summary, dict):
        sanitized_trace_summary = _load_json(sanitized_trace_path, {}) or {}

    missing_manifest_fields = [field for field in REQUIRED_MANIFEST_FIELDS if manifest.get(field) in (None, "")]
    acc = _number(metrics.get("acc", metrics.get("accuracy")))
    cost = _number(metrics.get("cost"))
    latency = _number(metrics.get("latency", metrics.get("latency_ms")))
    evaluation_status = str(metrics.get("evaluation_status") or "")
    validity_issues = metrics.get("artifact_validity_issues") or []
    resolved_score_sources = metrics.get("resolved_score_sources") or []
    resolved_result_sources = metrics.get("resolved_result_sources") or []
    metric_sources = metrics.get("metric_sources") or []
    source_summary = metrics.get("score_result_source_summary")
    if not isinstance(source_summary, dict):
        source_summary = {
            "score_source_count": len(resolved_score_sources) if isinstance(resolved_score_sources, list) else 0,
            "result_source_count": len(resolved_result_sources) if isinstance(resolved_result_sources, list) else 0,
            "metric_source_count": len(metric_sources) if isinstance(metric_sources, list) else 0,
        }
    candidate_record_path = _resolve_path(
        manifest.get("candidate_record_manifest_path")
        or manifest.get("candidate_records_path")
        or manifest.get("candidate_rules_path"),
        run_root,
    )
    candidate_records = _candidate_record_status(candidate_record_path) if manifest.get("kind") == "candidate" else None
    rule_snapshot_path = _resolve_path(
        manifest.get("active_rules_snapshot_path") or manifest.get("rule_snapshot_path") or manifest.get("rule_path"),
        run_root,
    )
    rule_snapshot_hash = manifest.get("active_rules_snapshot_hash") or manifest.get("rule_snapshot_hash") or manifest.get("rule_hash")
    computed_rule_snapshot_hash = _sha256(rule_snapshot_path) if rule_snapshot_path else None

    blockers: list[str] = []
    if not manifest_path.exists():
        blockers.append("run_manifest_missing")
    if not metrics_path.exists():
        blockers.append("metrics_missing")
    if missing_manifest_fields:
        blockers.append("run_manifest_required_fields_missing")
    if evaluation_status != "complete":
        blockers.append("evaluation_status_not_complete")
    if acc is None:
        blockers.append("accuracy_missing_or_not_numeric")
    if validity_issues:
        blockers.append("artifact_validity_issues_present")
    if not resolved_score_sources:
        blockers.append("resolved_score_sources_missing")
    if not resolved_result_sources:
        blockers.append("resolved_result_sources_missing")
    if not metric_sources:
        blockers.append("metric_sources_missing")
    if not isinstance(source_summary, dict) or not _positive_count(source_summary, "score_source_count"):
        blockers.append("score_source_summary_missing")
    if not isinstance(source_summary, dict) or not _positive_count(source_summary, "result_source_count"):
        blockers.append("result_source_summary_missing")
    if not isinstance(sanitized_trace_summary, dict) or not sanitized_trace_summary:
        blockers.append("sanitized_trace_summary_missing")
    elif sanitized_trace_summary.get("contains_raw_payloads") is True:
        blockers.append("sanitized_trace_summary_contains_raw_payloads")
    if _number(manifest.get("selected_case_count")) is None:
        blockers.append("selected_case_count_missing_or_not_numeric")
    if manifest.get("provider_preflight_passed") is not True:
        blockers.append("provider_preflight_not_marked_passed_in_manifest")
    if manifest.get("kind") == "candidate" and not manifest.get("rule_path"):
        blockers.append("candidate_rule_path_missing")
    if manifest.get("kind") == "candidate":
        if not rule_snapshot_path or not rule_snapshot_path.exists():
            blockers.append("candidate_rule_snapshot_missing")
        if not rule_snapshot_hash:
            blockers.append("candidate_rule_snapshot_hash_missing")
        if rule_snapshot_hash and computed_rule_snapshot_hash and rule_snapshot_hash != computed_rule_snapshot_hash:
            blockers.append("candidate_rule_snapshot_hash_mismatch")
        if not candidate_records or not candidate_records["passed"]:
            blockers.append("candidate_record_manifest_not_passed")
    if manifest.get("kind") == "baseline" and "baseline" not in str(manifest.get("comparison_line") or ""):
        blockers.append("baseline_comparison_line_invalid")
    if manifest.get("kind") not in {"baseline", "candidate", "bfcl_performance"}:
        blockers.append("run_kind_invalid")
    if preflight_path.exists() and preflight.get("passed") is False:
        blockers.append("run_preflight_failed")

    return {
        "report_scope": "bfcl_run_artifact_schema",
        "run_root": str(run_root),
        "run_artifact_schema_passed": not blockers,
        "manifest_path": str(manifest_path),
        "metrics_path": str(metrics_path),
        "preflight_path": str(preflight_path) if preflight_path.exists() else None,
        "sanitized_trace_summary_path": str(sanitized_trace_path) if sanitized_trace_path.exists() else None,
        "missing_manifest_fields": missing_manifest_fields,
        "manifest": manifest,
        "metrics": {
            "evaluation_status": evaluation_status or None,
            "accuracy": acc,
            "cost": cost,
            "latency": latency,
            "artifact_validity_issues": validity_issues,
            "resolved_score_sources": resolved_score_sources,
            "resolved_result_sources": resolved_result_sources,
            "metric_sources": metric_sources,
            "score_result_source_summary": source_summary,
            "sanitized_trace_summary": sanitized_trace_summary,
        },
        "candidate_records": candidate_records,
        "rule_snapshot": {
            "path": str(rule_snapshot_path) if rule_snapshot_path else None,
            "present": bool(rule_snapshot_path and rule_snapshot_path.exists()),
            "declared_hash": rule_snapshot_hash,
            "computed_hash": computed_rule_snapshot_hash,
        },
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_root", type=Path)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.run_root)
    print(json.dumps(report if not args.compact else {
        "run_artifact_schema_passed": report["run_artifact_schema_passed"],
        "blockers": report["blockers"],
        "missing_manifest_fields": report["missing_manifest_fields"],
    }, indent=2, sort_keys=True))
    if args.strict and not report["run_artifact_schema_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
