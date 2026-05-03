#!/usr/bin/env python3
"""Check the no-provider BFCL pre-generate substage observability patch gate."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_pregenerate_substage_observability_patch_gate_packet.json")
DEFAULT_SUMMARY = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_pregenerate_substage_observability_patch_summary.json")
FALSE_KEYS = (
    "authorized",
    "provider_request_authorized",
    "bfcl_generate_authorized",
    "bfcl_smoke_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
)
FUTURE_COMPACT_LABELS = [
    "config_source_exit_class",
    "env_default_expansion_class",
    "category_arg_assembly_shape",
    "category_arg_validation_result",
    "bfcl_cli_import_probe_class_without_generate",
    "bfcl_cli_argument_probe_class_without_generate",
    "pre_generate_marker_boundary_class",
    "last_started_stage",
    "last_completed_stage",
    "suspected_pregenerate_failure_substage",
]
REQUIRED_PATCH_POINTS = {
    "baseline_shell_stage_events_between_preflight_and_bfcl_generate",
    "generate_failure_telemetry_compact_record",
    "generate_failure_telemetry_artifact_checker_optional_future_fields",
}
REQUIRED_SUMMARY_PATCH_POINTS = {
    "run_bfcl_v4_baseline_stage_events",
    "run_bfcl_generate_failure_telemetry_compact_record",
    "generate_telemetry_artifact_checker_optional_future_fields",
}
IMPORT_PROBE_CLASSES = {"importable_without_generate", "import_error", "not_run_by_design", "unknown_compact"}
ARG_PROBE_CLASSES = {"argparse_ok_without_generate", "argparse_error_without_generate", "not_run_by_design", "unknown_compact"}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(secret_value|endpoint_value|api_key_value|raw_prompt|raw_case|raw_command|raw_log|raw_trace|raw_provider|provider_payload|raw_result_tree|prompt_text|case_content|trace_content|log_content|tool_argument_value|scorer_diff|candidate_output|gold_value|reference_value|expected_value)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint value|api key value|provider payload|raw prompt|raw case|raw command|raw log|raw trace|raw result tree|scorer diff|candidate output|openrouter|gpt-4o"),
    re.IGNORECASE,
)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain JSON object")
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


def _scan(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        key = path[-1] if path else ""
        parent = path[-2] if len(path) >= 2 else ""
        if key and parent != "forbidden_scope" and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "route_model" and value == "gpt-4.1":
                continue
            if parent == "forbidden_scope":
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if packet.get("artifact_kind") != "bfcl_pregenerate_substage_observability_patch_gate_packet":
        blockers.append(f"packet_artifact_kind_invalid:{packet.get('artifact_kind')!r}")
    if packet.get("approval_status") not in {"prepared", "pending"}:
        blockers.append(f"packet_approval_status_invalid:{packet.get('approval_status')!r}")
    if packet.get("route_profile") != "novacode" or packet.get("route_model") != "gpt-4.1":
        blockers.append("packet_route_drift")
    if packet.get("no_provider") is not True or packet.get("no_bfcl_execution") is not True:
        blockers.append("packet_no_provider_or_no_bfcl_execution_not_true")
    for key in FALSE_KEYS:
        if packet.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{packet.get(key)!r}")
    if packet.get("patch_authorization_scope") != "gate_only_no_behavior_patch":
        blockers.append(f"patch_authorization_scope_invalid:{packet.get('patch_authorization_scope')!r}")
    if packet.get("future_patch_scope") != "baseline_generate_telemetry_observability_only":
        blockers.append(f"future_patch_scope_invalid:{packet.get('future_patch_scope')!r}")
    for key, expected in (
        ("candidate_specs_inert", True),
        ("compact_only_policy", True),
        ("stop_before_evaluate_scorer_preserved", True),
        ("raw_logging_allowed", False),
        ("measurement_semantics_change_allowed", False),
        ("candidate_runtime_change_allowed", False),
    ):
        if packet.get(key) is not expected:
            blockers.append(f"packet_{key}_not_{str(expected).lower()}:{packet.get(key)!r}")
    if packet.get("allowed_future_compact_labels") != FUTURE_COMPACT_LABELS:
        blockers.append("allowed_future_compact_labels_invalid")
    patch_points = set(packet.get("required_future_patch_points", [])) if isinstance(packet.get("required_future_patch_points"), list) else set()
    if not patch_points.issuperset(REQUIRED_PATCH_POINTS):
        blockers.append("required_future_patch_points_missing")
    forbidden_scope = set(packet.get("forbidden_scope", [])) if isinstance(packet.get("forbidden_scope"), list) else set()
    for required in ("provider_call", "bfcl_generate", "bfcl_evaluate", "scorer", "full_baseline", "candidate_activation", "candidate_jsonl_or_pool", "performance_or_3pp_or_huawei_claim"):
        if required not in forbidden_scope:
            blockers.append(f"forbidden_scope_missing:{required}")
    blockers.extend(_scan(packet))
    return sorted(set(blockers))


def validate_summary(summary: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if summary.get("artifact_kind") != "bfcl_pregenerate_substage_observability_patch_summary":
        blockers.append(f"summary_artifact_kind_invalid:{summary.get('artifact_kind')!r}")
    if summary.get("no_provider") is not True or summary.get("no_bfcl_execution") is not True:
        blockers.append("summary_no_provider_or_no_bfcl_execution_not_true")
    if summary.get("behavior_patch_implemented") is not False or summary.get("patch_authorized") is not False:
        blockers.append("summary_patch_not_fail_closed")
    if summary.get("patch_scope_label") != "baseline_generate_telemetry_observability_only":
        blockers.append(f"summary_patch_scope_label_invalid:{summary.get('patch_scope_label')!r}")
    if summary.get("future_compact_labels") != FUTURE_COMPACT_LABELS:
        blockers.append("summary_future_compact_labels_invalid")
    if summary.get("labels_added_for_future_schema") != FUTURE_COMPACT_LABELS:
        blockers.append("summary_labels_added_for_future_schema_invalid")
    if summary.get("no_provider_import_probe_behavior") not in IMPORT_PROBE_CLASSES:
        blockers.append(f"summary_import_probe_behavior_invalid:{summary.get('no_provider_import_probe_behavior')!r}")
    if summary.get("no_provider_argument_probe_behavior") not in ARG_PROBE_CLASSES:
        blockers.append(f"summary_argument_probe_behavior_invalid:{summary.get('no_provider_argument_probe_behavior')!r}")
    if summary.get("no_provider_import_probe_behavior") != "not_run_by_design" or summary.get("no_provider_argument_probe_behavior") != "not_run_by_design":
        blockers.append("summary_probe_behavior_not_gate_safe")
    if not summary.get("probe_safety_rationale"):
        blockers.append("summary_probe_safety_rationale_missing")
    patch_points = set(summary.get("expected_patch_points", [])) if isinstance(summary.get("expected_patch_points"), list) else set()
    if not patch_points.issuperset(REQUIRED_SUMMARY_PATCH_POINTS):
        blockers.append("summary_expected_patch_points_missing")
    for key, expected in (
        ("preserve_compact_only_policy", True),
        ("preserve_stop_before_evaluate_scorer", True),
        ("candidate_runtime_unchanged", True),
        ("measurement_semantics_unchanged", True),
        ("raw_logging_added", False),
    ):
        if summary.get(key) is not expected:
            blockers.append(f"summary_{key}_not_{str(expected).lower()}:{summary.get(key)!r}")
    if not summary.get("suspected_gap"):
        blockers.append("summary_suspected_gap_missing")
    if not summary.get("next_gate_recommended"):
        blockers.append("summary_next_gate_recommended_missing")
    blockers.extend(_scan(summary))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, summary_path: Path = DEFAULT_SUMMARY) -> dict[str, Any]:
    packet = _load(packet_path)
    summary = _load(summary_path)
    blockers = sorted(set(validate_packet(packet) + validate_summary(summary)))
    return {
        "report_scope": "bfcl_pregenerate_substage_observability_patch_gate_check",
        "packet_path": str(packet_path),
        "summary_path": str(summary_path),
        "bfcl_pregenerate_substage_observability_patch_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "future_compact_label_count": len(summary.get("future_compact_labels", [])) if isinstance(summary.get("future_compact_labels"), list) else 0,
        "import_probe_behavior": summary.get("no_provider_import_probe_behavior"),
        "argument_probe_behavior": summary.get("no_provider_argument_probe_behavior"),
        "next_gate_recommended": summary.get("next_gate_recommended"),
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.summary)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_pregenerate_substage_observability_patch_gate_check", "bfcl_pregenerate_substage_observability_patch_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_pregenerate_substage_observability_patch_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
