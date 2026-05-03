#!/usr/bin/env python3
"""Check the sanitized BFCL proxy/preflight failure telemetry gate packet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_preflight_failure_telemetry_gate_packet.json")
REQUIRED_COMPACT_FIELDS = [
    "preflight_command_executed",
    "preflight_exact_exit_code_class",
    "preflight_failed_check_label",
    "preflight_environment_check_label",
    "proxy_health_at_preflight_start",
    "preflight_local_request_path_label",
    "preflight_http_status_class",
    "preflight_response_shape_label",
    "preflight_timeout_or_exception_class",
    "preflight_trace_emission_label",
    "preflight_report_written_label",
    "provider_call_started",
    "bfcl_generate_started",
    "bfcl_evaluate_started",
    "scorer_started",
    "candidate_specs_inert",
    "performance_evidence",
    "raw_outputs_removed",
    "stop_gate_triggered",
    "suspected_proxy_preflight_failure_stage",
]
APPROVAL_TRUE_KEYS = ("authorized", "proxy_live_preflight_authorized")
ALWAYS_FALSE_KEYS = (
    "provider_request_authorized",
    "bfcl_generate_authorized",
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
REQUIRED_STOP_GATES = {
    "provider_call_started",
    "bfcl_generate_started",
    "bfcl_evaluate_started",
    "scorer_started",
    "candidate_activation",
    "raw_or_secret_leak",
    "missing_sanitized_preflight_telemetry",
    "second_attempt_without_new_authorization",
    "output_boundary_failure",
}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_prompts?|raw_bfcl_case_content|raw_cases?|raw_provider_requests?|raw_provider_responses?|raw_response_headers?|raw_logs?|raw_traces?|raw_model_output_text|raw_tool_args?|raw_result_trees?|endpoint_values?|key_values?|api_key_values?|secret_values?|scorer_diffs?|candidate_outputs?|provider_payload_value|prompt_text|case_content|trace_content|log_content|tool_argument_value|gold_value|reference_value|expected_value)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint value|key value|api key|provider payload|raw prompt|raw case|raw log|raw trace|raw model output|raw tool arg|raw result tree|scorer diff|candidate output|openrouter|gpt-4o"),
    re.IGNORECASE,
)
ALLOWED_FORBIDDEN_LIST_VALUES = {
    "raw_prompt",
    "raw_bfcl_case_content",
    "raw_provider_request_body",
    "raw_provider_response_body",
    "raw_response_headers",
    "raw_logs",
    "raw_traces",
    "raw_model_output_text",
    "raw_tool_args",
    "raw_result_trees",
    "gold_reference_expected",
    "scorer_diff",
    "endpoint_key_value",
    "candidate_output",
}


def load_packet(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
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
        if key and parent != "forbidden_telemetry_content" and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "route_model" and value == "gpt-4.1":
                continue
            if parent == "forbidden_telemetry_content" and value in ALLOWED_FORBIDDEN_LIST_VALUES:
                continue
            if parent in {"future_stop_gates", "forbidden_scope"}:
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_proxy_preflight_failure_telemetry_gate_packet":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    status = data.get("approval_status")
    if status not in {"pending", "approved"}:
        blockers.append(f"approval_status_invalid:{status!r}")
    expected_true = status == "approved"
    for key in APPROVAL_TRUE_KEYS:
        if data.get(key) is not expected_true:
            blockers.append(f"{key}_not_{str(expected_true).lower()}:{data.get(key)!r}")
    for key in ALWAYS_FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    if data.get("requested_future_scope") != "one_sanitized_local_proxy_preflight_telemetry_attempt_only":
        blockers.append(f"requested_future_scope_invalid:{data.get('requested_future_scope')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    for key in (
        "compact_only",
        "one_attempt_only",
        "candidate_specs_inert",
        "provider_call_must_remain_false",
        "stop_before_bfcl_generate",
        "raw_output_cleanup_required",
    ):
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true:{data.get(key)!r}")

    fields = data.get("allowed_compact_fields")
    if not isinstance(fields, list):
        blockers.append("allowed_compact_fields_not_list")
        fields = []
    if fields != REQUIRED_COMPACT_FIELDS:
        missing = [field for field in REQUIRED_COMPACT_FIELDS if field not in fields]
        extra = [field for field in fields if field not in REQUIRED_COMPACT_FIELDS]
        if missing:
            blockers.append(f"missing_required_compact_fields:{missing!r}")
        if extra:
            blockers.append(f"extra_compact_fields:{extra!r}")
        if fields and not missing and not extra:
            blockers.append("allowed_compact_fields_order_invalid")
    for field in fields:
        if not isinstance(field, str):
            blockers.append(f"compact_field_not_string:{field!r}")
        elif FORBIDDEN_KEY_RE.search(field):
            blockers.append(f"forbidden_compact_field:{field}")
    for field in ("preflight_exact_exit_code_class", "preflight_failed_check_label", "provider_call_started", "stop_gate_triggered", "suspected_proxy_preflight_failure_stage"):
        if field not in fields:
            blockers.append(f"required_preflight_field_missing:{field}")

    stop_gates = set(data.get("future_stop_gates", [])) if isinstance(data.get("future_stop_gates"), list) else set()
    if not stop_gates.issuperset(REQUIRED_STOP_GATES):
        blockers.append("future_stop_gates_missing")
    forbidden_scope = set(data.get("forbidden_scope", [])) if isinstance(data.get("forbidden_scope"), list) else set()
    for required in (
        "provider_call",
        "bfcl_generate",
        "bfcl_evaluate",
        "scorer",
        "full_baseline",
        "candidate_activation",
        "candidate_jsonl_or_pool",
        "scorer_feedback_tuning",
        "baseline_vs_treatment_comparison",
        "performance_or_3pp_or_huawei_claim",
    ):
        if required not in forbidden_scope:
            blockers.append(f"forbidden_scope_missing:{required}")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = load_packet(path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "bfcl_proxy_preflight_failure_telemetry_gate_check",
        "packet_path": str(path),
        "bfcl_proxy_preflight_failure_telemetry_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "proxy_live_preflight_authorized": packet.get("proxy_live_preflight_authorized"),
        "provider_request_authorized": packet.get("provider_request_authorized"),
        "bfcl_generate_authorized": packet.get("bfcl_generate_authorized"),
        "route_profile": packet.get("route_profile"),
        "route_model": packet.get("route_model"),
        "compact_field_count": len(packet.get("allowed_compact_fields", [])) if isinstance(packet.get("allowed_compact_fields"), list) else 0,
        "performance_evidence": packet.get("performance_evidence"),
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_proxy_preflight_failure_telemetry_gate_check", "bfcl_proxy_preflight_failure_telemetry_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_proxy_preflight_failure_telemetry_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
