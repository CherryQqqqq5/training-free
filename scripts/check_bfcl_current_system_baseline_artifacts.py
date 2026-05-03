#!/usr/bin/env python3
"""Check compact current-system BFCL baseline artifacts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_compact_manifest.json")
DEFAULT_METRICS = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_compact_metrics.json")
DEFAULT_FAILURE = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_compact_failure_summary.json")
DEFAULT_RUN_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_current_system_baseline_compact_run_manifest.json")
REQUIRED_CATEGORIES = {
    "simple",
    "multiple",
    "parallel",
    "parallel_multiple",
    "multi_turn_base",
    "multi_turn_miss_func",
    "multi_turn_miss_param",
    "multi_turn_long_context",
}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(secret|endpoint_value|api_key|provider_payload|prompt|case_content|trace_content|log_content|tool_argument|scorer_diff|candidate_output|raw_path)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|openrouter|gpt-4o|candidate output|scorer diff|prompt text|case content|provider payload"),
    re.IGNORECASE,
)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _walk(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, path + (str(index),)))
    return items


def _scan(payloads: list[dict[str, Any]]) -> list[str]:
    blockers: list[str] = []
    for payload in payloads:
        for path, value in _walk(payload):
            key = path[-1] if path else ""
            dotted = ".".join(path)
            if key and FORBIDDEN_KEY_RE.search(key):
                blockers.append(f"forbidden_key:{dotted}")
            if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
                if key == "route_model" and value == "gpt-4.1":
                    continue
                if key == "bfcl_model_alias" and value == "gpt-4o-mini-2024-07-18-FC":
                    continue
                blockers.append(f"forbidden_value:{dotted}")
    return blockers


def _current_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def validate(manifest: dict[str, Any], metrics: dict[str, Any], failure: dict[str, Any], run_manifest: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if manifest.get("artifact_kind") != "bfcl_current_system_baseline_compact_manifest":
        blockers.append("manifest_kind_invalid")
    if metrics.get("artifact_kind") != "bfcl_current_system_baseline_compact_metrics":
        blockers.append("metrics_kind_invalid")
    if failure.get("artifact_kind") != "bfcl_current_system_baseline_compact_failure_summary":
        blockers.append("failure_kind_invalid")
    if run_manifest.get("artifact_kind") != "bfcl_current_system_baseline_compact_run_manifest":
        blockers.append("run_manifest_kind_invalid")
    for payload_name, payload in (("manifest", manifest), ("metrics", metrics), ("failure", failure), ("run_manifest", run_manifest)):
        if payload.get("measurement_kind") != "current_system_baseline_only":
            blockers.append(f"{payload_name}_measurement_kind_invalid")
        if payload.get("route_profile") != "novacode" or payload.get("route_model") != "gpt-4.1":
            blockers.append(f"{payload_name}_route_drift")
        for key in ("performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "candidate_specs_activated", "candidate_runtime_activation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready"):
            if key in payload and payload.get(key) is not False:
                blockers.append(f"{payload_name}_{key}_not_false")
        if payload.get("raw_outputs_committed") is not False:
            blockers.append(f"{payload_name}_raw_outputs_committed_not_false")
    if manifest.get("execution_commit") != _current_head():
        blockers.append("manifest_execution_commit_not_head")
    if manifest.get("target_commit") != "221e2b7c16247cb1886de4e3c6b38ea02c8b7bc8":
        blockers.append("target_commit_drift")
    if not (manifest.get("provider_call_executed") and manifest.get("bfcl_generate_executed") and manifest.get("bfcl_evaluate_executed") and manifest.get("scorer_executed") and manifest.get("full_baseline_executed")):
        blockers.append("baseline_execution_flags_missing")
    if manifest.get("baseline_vs_treatment_comparison") is not False:
        blockers.append("baseline_vs_treatment_comparison_not_false")
    categories = ((manifest.get("case_scope_protocol") or {}).get("categories") or [])
    if not set(categories).issuperset(REQUIRED_CATEGORIES):
        blockers.append("case_scope_categories_missing")
    if metrics.get("measurement_evidence") is not True:
        blockers.append("metrics_measurement_evidence_not_true")
    if metrics.get("performance_evidence") is not False:
        blockers.append("metrics_performance_evidence_not_false")
    if metrics.get("overall_accuracy") is None:
        blockers.append("overall_accuracy_missing")
    if not isinstance(metrics.get("subset_metrics"), dict) or not metrics.get("subset_metrics"):
        blockers.append("subset_metrics_missing")
    if metrics.get("scorer_feedback_used") is not False or run_manifest.get("scorer_feedback_used") is not False:
        blockers.append("scorer_feedback_used_not_false")
    if run_manifest.get("comparison_line") != "compatibility_baseline":
        blockers.append("comparison_line_invalid")
    blockers.extend(_scan([manifest, metrics, failure, run_manifest]))
    return sorted(set(blockers))


def check(manifest_path: Path = DEFAULT_MANIFEST, metrics_path: Path = DEFAULT_METRICS, failure_path: Path = DEFAULT_FAILURE, run_manifest_path: Path = DEFAULT_RUN_MANIFEST) -> dict[str, Any]:
    manifest = _load(manifest_path)
    metrics = _load(metrics_path)
    failure = _load(failure_path)
    run_manifest = _load(run_manifest_path)
    blockers = validate(manifest, metrics, failure, run_manifest)
    return {
        "report_scope": "bfcl_current_system_baseline_artifact_check",
        "baseline_artifacts_passed": not blockers,
        "compact_manifest": str(manifest_path),
        "compact_metrics": str(metrics_path),
        "compact_failure_summary": str(failure_path),
        "compact_run_manifest": str(run_manifest_path),
        "overall_accuracy": metrics.get("overall_accuracy"),
        "evaluation_status": metrics.get("evaluation_status"),
        "measurement_evidence": metrics.get("measurement_evidence"),
        "performance_evidence": metrics.get("performance_evidence"),
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--failure", type=Path, default=DEFAULT_FAILURE)
    parser.add_argument("--run-manifest", type=Path, default=DEFAULT_RUN_MANIFEST)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.manifest, args.metrics, args.failure, args.run_manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_current_system_baseline_artifact_check", "baseline_artifacts_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("baseline_artifacts_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
