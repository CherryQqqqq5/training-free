#!/usr/bin/env python3
"""Check compact proxy Responses tool-shape artifacts for leakage and scope drift."""

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

from scripts.check_bfcl_proxy_responses_tool_shape_gate import REQUIRED_COMPACT_FIELDS

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_responses_tool_shape_compact.json")
HTTP_STATUS_CLASSES = {"not_observed", "2xx", "3xx", "4xx", "5xx", "transport_error", "unknown"}
PROVIDER_HTTP_STATUS_LABELS = {"not_observed", "status_400", "status_401", "status_403", "status_404", "status_405", "status_415", "status_422", "status_429", "other_4xx", "status_5xx", "transport_error", "unknown"}
UPSTREAM_ROUTE_LABELS = {"not_reached", "local_proxy_responses_to_upstream_chat_completions"}
RESPONSE_JSON_PARSE_LABELS = {"parsed_json", "invalid_json", "empty_body", "not_read"}
RESPONSES_ENVELOPE_LABELS = {"not_checked", "responses_function_call", "responses_message_text", "responses_empty_output", "no_output", "malformed", "invalid_json", "non_2xx"}
TRACE_LABELS = {"not_observed", "trace_emitted", "trace_missing", "trace_deleted"}
TRACE_COUNT_CLASSES = {"not_observed", "zero", "one", "multiple"}
FAILED_CHECK_LABELS = {"none_observed", "packet_not_approved", "output_artifact_exists", "proxy_start_failed", "local_proxy_request_failed", "provider_transport_error", "provider_non_2xx", "responses_envelope_malformed", "responses_function_call_missing", "raw_or_secret_leak", "temp_raw_cleanup_failed", "unknown"}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_(requests?|responses?|bod(y|ies)|contents?|headers?|logs?|traces?|prompts?|cases?|tool_args?|provider_payloads?)|provider_payload|endpoint_values?|key_values?|api_key_values?|secret_values?|full_urls?|prompt_text|case_content|trace_content|log_content|tool_argument_value|gold_value|reference_value|expected_value|scorer_diffs?|candidate_outputs?|huawei_claim|performance_claim)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|api[_ -]?key|bearer |endpoint value|key value|full url|secret|provider payload|raw request|raw response|raw body|raw content|raw header|raw log|raw trace|raw prompt|raw case|raw tool arg|scorer diff|candidate output|huawei|\+3pp|performance evidence"),
    re.IGNORECASE,
)
ALLOWED_RAW_KEYS = {"raw_temp_outputs_removed", "raw_outputs_committed"}


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
        if key and key not in ALLOWED_RAW_KEYS and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{dotted}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "route_model" and value == "gpt-4.1":
                continue
            blockers.append(f"forbidden_value:{dotted}")
    return sorted(set(blockers))


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_proxy_responses_tool_shape_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("compact_schema_version") != "proxy_responses_tool_shape_v1":
        blockers.append(f"compact_schema_version_invalid:{data.get('compact_schema_version')!r}")
    if data.get("measurement_kind") != "compact_synthetic_proxy_responses_tool_shape_preflight":
        blockers.append(f"measurement_kind_invalid:{data.get('measurement_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    for key in (
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
            "proxy_started",
            "local_proxy_request_executed",
            "local_responses_path_selected",
            "upstream_provider_request_authorized",
            "upstream_provider_call_started",
            "response_body_read",
            "response_body_persisted",
            "function_call_present",
            "function_name_match",
            "raw_temp_outputs_removed",
            "raw_outputs_committed",
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
        if record.get("upstream_chat_route_label") not in UPSTREAM_ROUTE_LABELS:
            blockers.append(f"upstream_chat_route_label_invalid:{record.get('upstream_chat_route_label')!r}")
        if record.get("http_status_class") not in HTTP_STATUS_CLASSES:
            blockers.append(f"http_status_class_invalid:{record.get('http_status_class')!r}")
        if record.get("provider_http_status_label") not in PROVIDER_HTTP_STATUS_LABELS:
            blockers.append(f"provider_http_status_label_invalid:{record.get('provider_http_status_label')!r}")
        if record.get("response_json_parse_label") not in RESPONSE_JSON_PARSE_LABELS:
            blockers.append(f"response_json_parse_label_invalid:{record.get('response_json_parse_label')!r}")
        if record.get("responses_envelope_shape_label") not in RESPONSES_ENVELOPE_LABELS:
            blockers.append(f"responses_envelope_shape_label_invalid:{record.get('responses_envelope_shape_label')!r}")
        if record.get("trace_emission_label") not in TRACE_LABELS:
            blockers.append(f"trace_emission_label_invalid:{record.get('trace_emission_label')!r}")
        if record.get("trace_count_class") not in TRACE_COUNT_CLASSES:
            blockers.append(f"trace_count_class_invalid:{record.get('trace_count_class')!r}")
        if record.get("preflight_failed_check_label") not in FAILED_CHECK_LABELS:
            blockers.append(f"preflight_failed_check_label_invalid:{record.get('preflight_failed_check_label')!r}")
        for key in ("response_body_persisted", "raw_outputs_committed", "bfcl_generate_started", "bfcl_evaluate_started", "scorer_started", "full_baseline_executed", "source_collection_executed", "source_diagnostics_executed", "performance_evidence"):
            if record.get(key) is not False:
                blockers.append(f"{key}_not_false:{record.get(key)!r}")
        if record.get("candidate_specs_inert") is not True:
            blockers.append(f"candidate_specs_inert_not_true:{record.get('candidate_specs_inert')!r}")
        if record.get("preflight_command_executed") is True and record.get("raw_temp_outputs_removed") is not True:
            blockers.append(f"raw_temp_outputs_removed_not_true:{record.get('raw_temp_outputs_removed')!r}")
        if not record.get("stop_gate_triggered"):
            blockers.append("stop_gate_triggered_missing")
        if not record.get("suspected_failure_stage"):
            blockers.append("suspected_failure_stage_missing")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) and data.get("records") else {}
    return {
        "report_scope": "bfcl_proxy_responses_tool_shape_artifact_check",
        "artifact_path": str(path),
        "bfcl_proxy_responses_tool_shape_artifact_passed": not blockers,
        "proxy_started": record.get("proxy_started") if isinstance(record, dict) else None,
        "local_responses_path_selected": record.get("local_responses_path_selected") if isinstance(record, dict) else None,
        "upstream_chat_route_label": record.get("upstream_chat_route_label") if isinstance(record, dict) else None,
        "http_status_class": record.get("http_status_class") if isinstance(record, dict) else None,
        "provider_http_status_label": record.get("provider_http_status_label") if isinstance(record, dict) else None,
        "responses_envelope_shape_label": record.get("responses_envelope_shape_label") if isinstance(record, dict) else None,
        "function_call_present": record.get("function_call_present") if isinstance(record, dict) else None,
        "function_name_match": record.get("function_name_match") if isinstance(record, dict) else None,
        "response_body_read": record.get("response_body_read") if isinstance(record, dict) else None,
        "response_body_persisted": record.get("response_body_persisted") if isinstance(record, dict) else None,
        "trace_emission_label": record.get("trace_emission_label") if isinstance(record, dict) else None,
        "trace_count_class": record.get("trace_count_class") if isinstance(record, dict) else None,
        "raw_temp_outputs_removed": record.get("raw_temp_outputs_removed") if isinstance(record, dict) else None,
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
        summary = {"report_scope": "bfcl_proxy_responses_tool_shape_artifact_check", "bfcl_proxy_responses_tool_shape_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_proxy_responses_tool_shape_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
