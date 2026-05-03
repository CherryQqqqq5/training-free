#!/usr/bin/env python3
"""Check compact offline proxy upstream conformance diff artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_proxy_upstream_conformance_diff_gate import REQUIRED_COMPACT_FIELDS

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_upstream_conformance_diff_compact.json")
HEADER_SHAPE_LABELS = {"authorization_content_type_only", "authorization_content_type_extra", "missing_authorization", "missing_content_type", "unknown"}
PRESENCE_LABELS = {"present", "missing", "unknown"}
EXTRA_HEADER_LABELS = {"none", "referer_or_title_present", "other_extra", "unknown"}
ROLE_SEQUENCE_LABELS = {"user", "developer_user", "system_developer_user", "system_user", "malformed", "unknown"}
INJECTION_LABELS = {"present", "absent", "unknown"}
TEMPERATURE_LABELS = {"present_zero", "present_nonzero", "missing", "unknown"}
TOKEN_FIELD_LABELS = {"max_tokens", "max_output_tokens", "max_output_tokens_mapped_to_max_tokens", "missing", "unknown"}
TOOL_CHOICE_LABELS = {"chat_function_object", "required", "auto", "none", "missing", "malformed", "unknown"}
TOOLS_SHAPE_LABELS = {"chat_function_schema", "responses_function_schema", "missing", "malformed", "unknown"}
MODEL_LABELS = {"gpt_4_1", "other", "missing", "unknown"}
RUNTIME_PATCH_LABELS = {"nonzero_policy_patch", "zero_policy_patch", "unknown"}
ADAPTER_LABELS = {"responses_to_chat_applied", "not_applied", "malformed", "unknown"}
CAUSE_LABELS = {"policy_message_shape_drift", "temperature_missing_with_policy_drift", "header_shape_drift", "model_drift", "none_observed", "unknown"}
CONFORMANCE_LABELS = {"matched_direct_chat_tool_shape", "partial_drift_headers_aligned", "header_drift", "model_drift", "unknown"}
STOP_LABELS = {"none", "stopped_after_fake_upstream_capture", "packet_not_approved", "output_artifact_exists", "unknown"}
FAILED_CHECK_LABELS = {"none_observed", "packet_not_approved", "output_artifact_exists", "raw_or_secret_leak", "unknown"}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_(requests?|responses?|bod(y|ies)|contents?|headers?|logs?|traces?|prompts?|cases?|tool_args?|provider_payloads?)|provider_payload|endpoint_values?|key_values?|api_key_values?|secret_values?|full_urls?|prompt_text|case_content|trace_content|log_content|tool_argument_value|gold_value|reference_value|expected_value|scorer_diffs?|candidate_outputs?|huawei_claim|performance_claim)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|bearer |endpoint value|key value|full url|secret|provider payload|raw request|raw response|raw body|raw content|raw header|raw log|raw trace|raw prompt|raw case|raw tool arg|scorer diff|candidate output|huawei|\+3pp|performance evidence"),
    re.IGNORECASE,
)
ALLOWED_FIELD_NAMES = set(REQUIRED_COMPACT_FIELDS)


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
        dotted = ".".join(path)
        if key and key not in ALLOWED_FIELD_NAMES and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{dotted}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "route_model" and value == "gpt-4.1":
                continue
            blockers.append(f"forbidden_value:{dotted}")
    return sorted(set(blockers))


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_proxy_upstream_conformance_diff_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("compact_schema_version") != "proxy_upstream_conformance_diff_v1":
        blockers.append(f"compact_schema_version_invalid:{data.get('compact_schema_version')!r}")
    if data.get("measurement_kind") != "compact_offline_proxy_upstream_conformance_header_policy_diff":
        blockers.append(f"measurement_kind_invalid:{data.get('measurement_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    for key in (
        "provider_call_executed",
        "proxy_live_request_executed",
        "profile_sourced_summary",
        "bfcl_generate_executed",
        "bfcl_evaluate_executed",
        "scorer_executed",
        "full_baseline_executed",
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "source_collection_executed",
        "source_diagnostics_executed",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
        "raw_outputs_committed",
    ):
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    records = data.get("records")
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        blockers.append("records_invalid")
        record: dict[str, Any] = {}
    else:
        record = records[0]
    if record:
        missing = [field for field in REQUIRED_COMPACT_FIELDS if field not in record]
        extra = [field for field in record if field not in REQUIRED_COMPACT_FIELDS]
        if missing:
            blockers.append(f"missing_required_fields:{missing!r}")
        if extra:
            blockers.append(f"extra_fields:{extra!r}")
        for key in (
            "preflight_command_executed",
            "provider_call_started",
            "profile_sourced",
            "proxy_live_request_started",
            "fake_upstream_capture_used",
            "raw_outputs_committed",
            "raw_temp_outputs_removed",
            "bfcl_generate_started",
            "bfcl_evaluate_started",
            "scorer_started",
            "full_baseline_executed",
            "candidate_specs_inert",
            "source_collection_executed",
            "source_diagnostics_executed",
            "performance_evidence",
        ):
            if record.get(key) not in (True, False):
                blockers.append(f"{key}_not_bool:{record.get(key)!r}")
        for key in (
            "provider_call_started",
            "profile_sourced",
            "proxy_live_request_started",
            "raw_outputs_committed",
            "bfcl_generate_started",
            "bfcl_evaluate_started",
            "scorer_started",
            "full_baseline_executed",
            "source_collection_executed",
            "source_diagnostics_executed",
            "performance_evidence",
        ):
            if record.get(key) is not False:
                blockers.append(f"{key}_not_false:{record.get(key)!r}")
        if record.get("fake_upstream_capture_used") is not True:
            blockers.append(f"fake_upstream_capture_used_not_true:{record.get('fake_upstream_capture_used')!r}")
        if record.get("raw_temp_outputs_removed") is not True:
            blockers.append(f"raw_temp_outputs_removed_not_true:{record.get('raw_temp_outputs_removed')!r}")
        if record.get("candidate_specs_inert") is not True:
            blockers.append(f"candidate_specs_inert_not_true:{record.get('candidate_specs_inert')!r}")
        validations = {
            "provider_facing_header_shape_label": HEADER_SHAPE_LABELS,
            "authorization_header_presence_label": PRESENCE_LABELS,
            "content_type_header_label": PRESENCE_LABELS,
            "extra_provider_header_shape_label": EXTRA_HEADER_LABELS,
            "messages_role_sequence_label": ROLE_SEQUENCE_LABELS,
            "system_injection_label": INJECTION_LABELS,
            "developer_instruction_label": INJECTION_LABELS,
            "temperature_field_label": TEMPERATURE_LABELS,
            "token_field_label": TOKEN_FIELD_LABELS,
            "tool_choice_shape_label": TOOL_CHOICE_LABELS,
            "tools_shape_label": TOOLS_SHAPE_LABELS,
            "model_label": MODEL_LABELS,
            "runtime_patch_label": RUNTIME_PATCH_LABELS,
            "responses_to_chat_adapter_label": ADAPTER_LABELS,
            "suspected_403_cause_label": CAUSE_LABELS,
            "direct_proxy_conformance_label": CONFORMANCE_LABELS,
            "stop_gate_triggered": STOP_LABELS,
            "preflight_failed_check_label": FAILED_CHECK_LABELS,
        }
        for key, allowed in validations.items():
            if record.get(key) not in allowed:
                blockers.append(f"{key}_invalid:{record.get(key)!r}")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) and data.get("records") else {}
    return {
        "report_scope": "bfcl_proxy_upstream_conformance_diff_artifact_check",
        "artifact_path": str(path),
        "bfcl_proxy_upstream_conformance_diff_artifact_passed": not blockers,
        "provider_facing_header_shape_label": record.get("provider_facing_header_shape_label") if isinstance(record, dict) else None,
        "authorization_header_presence_label": record.get("authorization_header_presence_label") if isinstance(record, dict) else None,
        "content_type_header_label": record.get("content_type_header_label") if isinstance(record, dict) else None,
        "extra_provider_header_shape_label": record.get("extra_provider_header_shape_label") if isinstance(record, dict) else None,
        "messages_role_sequence_label": record.get("messages_role_sequence_label") if isinstance(record, dict) else None,
        "system_injection_label": record.get("system_injection_label") if isinstance(record, dict) else None,
        "developer_instruction_label": record.get("developer_instruction_label") if isinstance(record, dict) else None,
        "temperature_field_label": record.get("temperature_field_label") if isinstance(record, dict) else None,
        "token_field_label": record.get("token_field_label") if isinstance(record, dict) else None,
        "tool_choice_shape_label": record.get("tool_choice_shape_label") if isinstance(record, dict) else None,
        "tools_shape_label": record.get("tools_shape_label") if isinstance(record, dict) else None,
        "model_label": record.get("model_label") if isinstance(record, dict) else None,
        "runtime_patch_label": record.get("runtime_patch_label") if isinstance(record, dict) else None,
        "responses_to_chat_adapter_label": record.get("responses_to_chat_adapter_label") if isinstance(record, dict) else None,
        "suspected_403_cause_label": record.get("suspected_403_cause_label") if isinstance(record, dict) else None,
        "direct_proxy_conformance_label": record.get("direct_proxy_conformance_label") if isinstance(record, dict) else None,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_proxy_upstream_conformance_diff_artifact_check", "bfcl_proxy_upstream_conformance_diff_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_proxy_upstream_conformance_diff_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
