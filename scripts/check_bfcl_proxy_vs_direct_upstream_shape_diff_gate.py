#!/usr/bin/env python3
"""Check the pending proxy-vs-direct upstream shape-diff gate packet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_vs_direct_upstream_shape_diff_gate_packet.json")
REQUIRED_COMPACT_FIELDS = [
    "preflight_command_executed",
    "direct_selected_api_key_env_label",
    "proxy_selected_api_key_env_label",
    "api_key_env_match",
    "direct_selected_base_url_env_label",
    "proxy_selected_base_url_env_label",
    "base_url_env_match",
    "model_label_match",
    "tool_choice_shape_label",
    "tools_shape_label",
    "messages_shape_label",
    "token_field_shape_label",
    "runtime_patch_label",
    "suspected_mismatch_label",
    "provider_call_started",
    "proxy_live_request_started",
    "profile_sourced",
    "bfcl_generate_started",
    "bfcl_evaluate_started",
    "scorer_started",
    "full_baseline_executed",
    "candidate_specs_inert",
    "source_collection_executed",
    "source_diagnostics_executed",
    "performance_evidence",
    "raw_outputs_committed",
    "stop_gate_triggered",
    "preflight_failed_check_label",
]
APPROVAL_TRUE_KEYS = ("authorized",)
ALWAYS_FALSE_KEYS = (
    "provider_request_authorized",
    "proxy_live_request_authorized",
    "profile_source_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "source_collection_authorized",
    "source_diagnostics_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
)
REQUIRED_TRUE_KEYS = ("compact_only", "one_attempt_only", "synthetic_probe_only", "fail_if_output_artifact_exists", "raw_output_cleanup_required")
REQUIRED_STOP_GATES = {
    "packet_not_approved",
    "output_artifact_exists",
    "raw_or_secret_leak",
    "profile_source_attempted",
    "provider_call_started",
    "proxy_live_request_started",
    "bfcl_generate_started",
    "bfcl_evaluate_started",
    "scorer_started",
    "full_baseline_started",
    "candidate_activation",
    "source_collection",
    "performance_evidence",
}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_(requests?|responses?|bod(y|ies)|contents?|headers?|logs?|traces?|prompts?|cases?|tool_args?|provider_payloads?)|provider_payload|endpoint_values?|key_values?|api_key_values?|secret_values?|full_urls?|prompt_text|case_content|trace_content|log_content|tool_argument_value|gold_value|reference_value|expected_value|scorer_diffs?|candidate_outputs?|huawei_claim|performance_claim|headers?)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|bearer |endpoint value|key value|full url|secret|provider payload|raw request|raw response|raw body|raw content|raw header|raw log|raw trace|raw prompt|raw case|raw tool arg|scorer diff|candidate output|huawei|\+3pp|performance evidence"),
    re.IGNORECASE,
)
ALLOWED_FIELD_NAMES = set(REQUIRED_COMPACT_FIELDS) | set(APPROVAL_TRUE_KEYS) | set(ALWAYS_FALSE_KEYS) | set(REQUIRED_TRUE_KEYS) | {"raw_output_cleanup_required"}


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
        dotted = ".".join(path)
        if key and key not in ALLOWED_FIELD_NAMES and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{dotted}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "route_model" and value == "gpt-4.1":
                continue
            if parent in {"allowed_compact_fields", "future_stop_gates"}:
                continue
            blockers.append(f"forbidden_value:{dotted}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_proxy_vs_direct_upstream_shape_diff_gate_packet":
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
    for key in REQUIRED_TRUE_KEYS:
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true:{data.get(key)!r}")
    if data.get("requested_scope") != "static_no_provider_proxy_vs_direct_upstream_shape_diff_only":
        blockers.append(f"requested_scope_invalid:{data.get('requested_scope')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
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
        elif field not in REQUIRED_COMPACT_FIELDS or FORBIDDEN_KEY_RE.search(field):
            blockers.append(f"forbidden_compact_field:{field}")
    stop_gates = set(data.get("future_stop_gates", [])) if isinstance(data.get("future_stop_gates"), list) else set()
    if not stop_gates.issuperset(REQUIRED_STOP_GATES):
        blockers.append("future_stop_gates_missing")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = load_packet(path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "bfcl_proxy_vs_direct_upstream_shape_diff_gate_check",
        "packet_path": str(path),
        "bfcl_proxy_vs_direct_upstream_shape_diff_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "provider_request_authorized": packet.get("provider_request_authorized"),
        "proxy_live_request_authorized": packet.get("proxy_live_request_authorized"),
        "profile_source_authorized": packet.get("profile_source_authorized"),
        "route_profile": packet.get("route_profile"),
        "route_model": packet.get("route_model"),
        "compact_field_count": len(packet.get("allowed_compact_fields", [])) if isinstance(packet.get("allowed_compact_fields"), list) else 0,
        "bfcl_generate_authorized": packet.get("bfcl_generate_authorized"),
        "bfcl_evaluate_authorized": packet.get("bfcl_evaluate_authorized"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "full_baseline_authorized": packet.get("full_baseline_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
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
        summary = {"report_scope": "bfcl_proxy_vs_direct_upstream_shape_diff_gate_check", "bfcl_proxy_vs_direct_upstream_shape_diff_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_proxy_vs_direct_upstream_shape_diff_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
