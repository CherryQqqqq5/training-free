#!/usr/bin/env python3
"""Check compact offline proxy transport request capture diff artifacts."""

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

from scripts.check_bfcl_proxy_transport_request_capture_diff_gate import REQUIRED_COMPACT_FIELDS

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_transport_request_capture_diff_compact.json")
TRANSPORT_CLIENT_LABELS = {"httpx_async_client_post", "urllib_request", "unknown"}
CLIENT_STACK_LABELS = {"proxy_httpx_json_kwarg", "proxy_httpx_content_bytes", "direct_urllib_manual_bytes", "unknown"}
BODY_SUBMISSION_LABELS = {"httpx_json_kwarg", "content_bytes", "data_bytes", "urllib_data_bytes", "unknown"}
JSON_SERIALIZATION_LABELS = {"httpx_json_parameter", "manual_json_compact_bytes", "unknown"}
PRESENCE_LABELS = {"present", "missing", "unknown"}
AUTH_SCHEME_LABELS = {"bearer", "missing", "unknown"}
EXTRA_HEADER_LABELS = {"none", "referer_or_title_possible", "other_extra", "unknown"}
HEADER_SHAPE_LABELS = {"authorization_content_type_only", "authorization_content_type_extra", "missing_authorization", "missing_content_type", "unknown"}
URL_JOIN_LABELS = {"base_url_chat_completions_appended", "direct_target_url_supplied", "unknown"}
TARGET_SUFFIX_LABELS = {"chat_completions_suffix", "unknown"}
TIMEOUT_LABELS = {"config_timeout_sec", "urllib_timeout_30", "unknown"}
PAYLOAD_MATCH_LABELS = {"matched_direct_chat_tool_shape", "transport_only_payload_not_compared", "mismatch", "unknown"}
PAYLOAD_SHAPE_LABELS = {"chat_tool_direct_aligned", "chat_tool_shape_drift", "unknown"}
BASE_URL_ENV_LABELS = {"GRC_UPSTREAM_BASE_URL", "NOVACODE_BASE_URL", "GRC_UPSTREAM_BASE_URL_then_NOVACODE_BASE_URL", "unknown"}
API_KEY_ENV_LABELS = {"CHUANGZHI_API_KEY", "NOVACODE_API_KEY", "unknown"}
PROXY_PYTHON_LABELS = {"grc_python_env", "repo_venv", "caller_python", "not_used"}
CAUSE_LABELS = {"transport_stack_or_serialization_drift", "transport_patch_ready", "header_shape_drift", "url_join_or_provider_policy", "payload_shape_drift", "none_observed", "unknown"}
STOP_LABELS = {"none", "stopped_after_fake_transport_capture", "packet_not_approved", "output_artifact_exists", "unknown"}
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
    if data.get("artifact_kind") != "bfcl_proxy_transport_request_capture_diff_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("compact_schema_version") != "proxy_transport_request_capture_diff_v1":
        blockers.append(f"compact_schema_version_invalid:{data.get('compact_schema_version')!r}")
    if data.get("measurement_kind") != "compact_offline_proxy_transport_request_capture_diff":
        blockers.append(f"measurement_kind_invalid:{data.get('measurement_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    for key in (
        "provider_call_executed", "proxy_live_request_executed", "profile_sourced_summary",
        "bfcl_generate_executed", "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed",
        "candidate_runtime_activation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready",
        "source_collection_executed", "source_diagnostics_executed", "performance_evidence",
        "sota_3pp_claim_ready", "huawei_acceptance_ready", "raw_outputs_committed",
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
            "preflight_command_executed", "provider_call_started", "profile_sourced", "proxy_live_request_started",
            "fake_transport_capture_used", "raw_outputs_committed", "raw_temp_outputs_removed",
            "bfcl_generate_started", "bfcl_evaluate_started", "scorer_started", "full_baseline_executed",
            "candidate_specs_inert", "source_collection_executed", "source_diagnostics_executed", "performance_evidence",
        ):
            if record.get(key) not in (True, False):
                blockers.append(f"{key}_not_bool:{record.get(key)!r}")
        for key in (
            "provider_call_started", "profile_sourced", "proxy_live_request_started", "raw_outputs_committed",
            "bfcl_generate_started", "bfcl_evaluate_started", "scorer_started", "full_baseline_executed",
            "source_collection_executed", "source_diagnostics_executed", "performance_evidence",
        ):
            if record.get(key) is not False:
                blockers.append(f"{key}_not_false:{record.get(key)!r}")
        if record.get("fake_transport_capture_used") is not True:
            blockers.append(f"fake_transport_capture_used_not_true:{record.get('fake_transport_capture_used')!r}")
        if record.get("raw_temp_outputs_removed") is not True:
            blockers.append(f"raw_temp_outputs_removed_not_true:{record.get('raw_temp_outputs_removed')!r}")
        if record.get("candidate_specs_inert") is not True:
            blockers.append(f"candidate_specs_inert_not_true:{record.get('candidate_specs_inert')!r}")
        validations = {
            "transport_client_label": TRANSPORT_CLIENT_LABELS,
            "client_stack_label": CLIENT_STACK_LABELS,
            "body_submission_label": BODY_SUBMISSION_LABELS,
            "json_serialization_label": JSON_SERIALIZATION_LABELS,
            "content_type_header_label": PRESENCE_LABELS,
            "authorization_header_label": PRESENCE_LABELS,
            "auth_scheme_label": AUTH_SCHEME_LABELS,
            "extra_header_shape_label": EXTRA_HEADER_LABELS,
            "provider_header_shape_label": HEADER_SHAPE_LABELS,
            "url_join_label": URL_JOIN_LABELS,
            "request_target_suffix_label": TARGET_SUFFIX_LABELS,
            "timeout_shape_label": TIMEOUT_LABELS,
            "payload_shape_match_label": PAYLOAD_MATCH_LABELS,
            "payload_shape_label": PAYLOAD_SHAPE_LABELS,
            "selected_base_url_env_label": BASE_URL_ENV_LABELS,
            "selected_api_key_env_label": API_KEY_ENV_LABELS,
            "proxy_python_label": PROXY_PYTHON_LABELS,
            "suspected_403_cause_label": CAUSE_LABELS,
            "direct_transport_client_label": TRANSPORT_CLIENT_LABELS,
            "direct_body_submission_label": BODY_SUBMISSION_LABELS,
            "direct_json_serialization_label": JSON_SERIALIZATION_LABELS,
            "direct_timeout_shape_label": TIMEOUT_LABELS,
            "direct_header_shape_label": HEADER_SHAPE_LABELS,
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
        "report_scope": "bfcl_proxy_transport_request_capture_diff_artifact_check",
        "artifact_path": str(path),
        "bfcl_proxy_transport_request_capture_diff_artifact_passed": not blockers,
        "transport_client_label": record.get("transport_client_label") if isinstance(record, dict) else None,
        "client_stack_label": record.get("client_stack_label") if isinstance(record, dict) else None,
        "body_submission_label": record.get("body_submission_label") if isinstance(record, dict) else None,
        "json_serialization_label": record.get("json_serialization_label") if isinstance(record, dict) else None,
        "provider_header_shape_label": record.get("provider_header_shape_label") if isinstance(record, dict) else None,
        "auth_scheme_label": record.get("auth_scheme_label") if isinstance(record, dict) else None,
        "url_join_label": record.get("url_join_label") if isinstance(record, dict) else None,
        "request_target_suffix_label": record.get("request_target_suffix_label") if isinstance(record, dict) else None,
        "timeout_shape_label": record.get("timeout_shape_label") if isinstance(record, dict) else None,
        "payload_shape_match_label": record.get("payload_shape_match_label") if isinstance(record, dict) else None,
        "selected_base_url_env_label": record.get("selected_base_url_env_label") if isinstance(record, dict) else None,
        "selected_api_key_env_label": record.get("selected_api_key_env_label") if isinstance(record, dict) else None,
        "suspected_403_cause_label": record.get("suspected_403_cause_label") if isinstance(record, dict) else None,
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
        summary = {"report_scope": "bfcl_proxy_transport_request_capture_diff_artifact_check", "bfcl_proxy_transport_request_capture_diff_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_proxy_transport_request_capture_diff_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
