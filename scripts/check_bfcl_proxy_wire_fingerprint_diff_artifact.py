#!/usr/bin/env python3
"""Check compact offline proxy prepared-request/wire-fingerprint diff artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_bfcl_proxy_wire_fingerprint_diff_gate import REQUIRED_COMPACT_FIELDS

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_wire_fingerprint_diff_compact.json")
STACK_LABELS = {"urllib_request", "httpx_async_client", "unknown"}
METHOD_LABELS = {"post", "unknown"}
SUFFIX_LABELS = {"chat_completions_suffix", "unknown"}
TARGET_LABELS = {"chat_completions_target", "unknown"}
HEADER_SET_LABELS = {"authorization_content_type_only", "authorization_content_type_content_length_httpx_defaults", "unknown"}
DEFAULT_HEADER_LABELS = {"proxy_httpx_defaults_present_direct_not_observed", "not_observed", "unknown"}
WIRE_PRESENCE_LABELS = {"present", "absent", "proxy_present_direct_not_observed", "not_observed", "unknown"}
CONTENT_LENGTH_LABELS = {"both_nonzero", "proxy_nonzero_direct_not_observed", "missing", "unknown"}
TRANSFER_LABELS = {"absent", "present", "not_observed", "unknown"}
BODY_SHAPE_LABELS = {"both_compact_json_nonzero", "proxy_only_nonzero", "mismatch_or_not_observed", "unknown"}
PROXY_ENV_LABELS = {"proxy_env_names_present", "proxy_env_names_absent", "not_observed", "unknown"}
TRUST_ENV_LABELS = {"true", "false", "not_observed", "unknown"}
HTTP2_LABELS = {"false", "true", "not_observed", "unknown"}
TIMEOUT_LABELS = {"proxy_config_timeout_direct_urllib_timeout", "not_observed", "unknown"}
TLS_LABELS = {"not_observed", "default_context_uninspected", "unknown"}
CAUSE_LABELS = {"httpx_default_header_context_diff", "body_shape_or_serialization_diff", "none_observed", "not_observed", "unknown"}
STOP_LABELS = {"none", "stopped_after_prepared_request_capture", "packet_not_approved", "output_artifact_exists", "raw_or_secret_leak", "unknown"}
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


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain JSON object" % path)
    return data


def _walk(value: Any, path: Tuple[str, ...] = ()) -> List[Tuple[Tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, path + (str(index),)))
    return items


def _scan(data: Dict[str, Any]) -> List[str]:
    blockers = []
    for path, value in _walk(data):
        key = path[-1] if path else ""
        dotted = ".".join(path)
        if key and key not in ALLOWED_FIELD_NAMES and FORBIDDEN_KEY_RE.search(key):
            blockers.append("forbidden_key:%s" % dotted)
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "route_model" and value == "gpt-4.1":
                continue
            blockers.append("forbidden_value:%s" % dotted)
    return sorted(set(blockers))


def validate(data: Dict[str, Any]) -> List[str]:
    blockers = []
    if data.get("artifact_kind") != "bfcl_proxy_wire_fingerprint_diff_compact":
        blockers.append("artifact_kind_invalid:%r" % data.get("artifact_kind"))
    if data.get("compact_schema_version") != "proxy_wire_fingerprint_diff_v1":
        blockers.append("compact_schema_version_invalid:%r" % data.get("compact_schema_version"))
    if data.get("measurement_kind") != "compact_offline_proxy_prepared_request_wire_fingerprint_diff":
        blockers.append("measurement_kind_invalid:%r" % data.get("measurement_kind"))
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
            blockers.append("%s_not_false:%r" % (key, data.get(key)))
    records = data.get("records")
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        blockers.append("records_invalid")
        record = {}
    else:
        record = records[0]
    if record:
        missing = [field for field in REQUIRED_COMPACT_FIELDS if field not in record]
        extra = [field for field in record if field not in REQUIRED_COMPACT_FIELDS]
        if missing:
            blockers.append("missing_required_fields:%r" % missing)
        if extra:
            blockers.append("extra_fields:%r" % extra)
        bool_keys = (
            "preflight_command_executed", "provider_call_started", "profile_sourced", "proxy_live_request_started",
            "fake_transport_capture_used", "prepared_request_capture_used", "raw_outputs_committed", "raw_temp_outputs_removed",
            "bfcl_generate_started", "bfcl_evaluate_started", "scorer_started", "full_baseline_executed",
            "candidate_specs_inert", "source_collection_executed", "source_diagnostics_executed", "performance_evidence",
        )
        for key in bool_keys:
            if record.get(key) not in (True, False):
                blockers.append("%s_not_bool:%r" % (key, record.get(key)))
        for key in (
            "provider_call_started", "profile_sourced", "proxy_live_request_started", "raw_outputs_committed",
            "bfcl_generate_started", "bfcl_evaluate_started", "scorer_started", "full_baseline_executed",
            "source_collection_executed", "source_diagnostics_executed", "performance_evidence",
        ):
            if record.get(key) is not False:
                blockers.append("%s_not_false:%r" % (key, record.get(key)))
        for key in ("fake_transport_capture_used", "prepared_request_capture_used", "raw_temp_outputs_removed", "candidate_specs_inert"):
            if record.get(key) is not True:
                blockers.append("%s_not_true:%r" % (key, record.get(key)))
        validations = {
            "direct_client_stack_label": STACK_LABELS,
            "proxy_client_stack_label": STACK_LABELS,
            "method_label": METHOD_LABELS,
            "url_suffix_label": SUFFIX_LABELS,
            "wire_request_target_label": TARGET_LABELS,
            "header_name_set_label": HEADER_SET_LABELS,
            "direct_header_name_set_label": HEADER_SET_LABELS,
            "default_header_shape_label": DEFAULT_HEADER_LABELS,
            "wire_user_agent_label": WIRE_PRESENCE_LABELS,
            "wire_accept_label": WIRE_PRESENCE_LABELS,
            "wire_accept_encoding_label": WIRE_PRESENCE_LABELS,
            "wire_connection_label": WIRE_PRESENCE_LABELS,
            "content_length_shape_label": CONTENT_LENGTH_LABELS,
            "transfer_encoding_label": TRANSFER_LABELS,
            "body_bytes_shape_match_label": BODY_SHAPE_LABELS,
            "proxy_env_presence_label": PROXY_ENV_LABELS,
            "trust_env_label": TRUST_ENV_LABELS,
            "http2_config_label": HTTP2_LABELS,
            "timeout_shape_label": TIMEOUT_LABELS,
            "tls_context_source_label": TLS_LABELS,
            "suspected_403_cause_label": CAUSE_LABELS,
            "stop_gate_triggered": STOP_LABELS,
            "preflight_failed_check_label": FAILED_CHECK_LABELS,
        }
        for key, allowed in validations.items():
            if record.get(key) not in allowed:
                blockers.append("%s_invalid:%r" % (key, record.get(key)))
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> Dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) and data.get("records") else {}
    return {
        "report_scope": "bfcl_proxy_wire_fingerprint_diff_artifact_check",
        "artifact_path": str(path),
        "bfcl_proxy_wire_fingerprint_diff_artifact_passed": not blockers,
        "direct_client_stack_label": record.get("direct_client_stack_label") if isinstance(record, dict) else None,
        "proxy_client_stack_label": record.get("proxy_client_stack_label") if isinstance(record, dict) else None,
        "method_label": record.get("method_label") if isinstance(record, dict) else None,
        "url_suffix_label": record.get("url_suffix_label") if isinstance(record, dict) else None,
        "wire_request_target_label": record.get("wire_request_target_label") if isinstance(record, dict) else None,
        "header_name_set_label": record.get("header_name_set_label") if isinstance(record, dict) else None,
        "default_header_shape_label": record.get("default_header_shape_label") if isinstance(record, dict) else None,
        "body_bytes_shape_match_label": record.get("body_bytes_shape_match_label") if isinstance(record, dict) else None,
        "trust_env_label": record.get("trust_env_label") if isinstance(record, dict) else None,
        "http2_config_label": record.get("http2_config_label") if isinstance(record, dict) else None,
        "suspected_403_cause_label": record.get("suspected_403_cause_label") if isinstance(record, dict) else None,
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_proxy_wire_fingerprint_diff_artifact_check", "bfcl_proxy_wire_fingerprint_diff_artifact_passed": False, "blockers": ["load_failed:%s" % exc]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_proxy_wire_fingerprint_diff_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
