#!/usr/bin/env python3
"""Check compact sanitized BFCL proxy/preflight failure telemetry artifact."""

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

from scripts.check_bfcl_proxy_preflight_failure_telemetry_gate import REQUIRED_COMPACT_FIELDS

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_preflight_failure_telemetry_compact.json")
EXIT_CODE_CLASSES = {"zero", "nonzero_1", "nonzero_other"}
FAILED_CHECK_LABELS = {"none_observed", "environment_check", "chat_tool_call", "responses_function_call", "chat_text_response", "trace_emission", "preflight_report_missing", "unknown_compact"}
ENV_LABELS = {"ok", "missing_required_env", "not_observed", "unknown_compact"}
PROXY_HEALTH_LABELS = {"healthy_preflight_started", "proxy_start_incomplete", "not_reached", "unknown_compact"}
REQUEST_PATH_LABELS = {"local_proxy_chat_and_responses_paths", "local_proxy_chat_path_only", "local_proxy_responses_path_only", "not_observed", "unknown_compact"}
HTTP_STATUS_LABELS = {"2xx", "3xx", "4xx", "5xx", "mixed_non2xx", "not_observed", "unknown_compact"}
RESPONSE_SHAPE_LABELS = {"all_expected_shapes", "missing_tool_call", "missing_function_call", "missing_text", "not_observed", "unknown_compact"}
TIMEOUT_EXCEPTION_LABELS = {"none_observed", "timeout", "http_error", "runtime_exception", "unknown_compact"}
TRACE_LABELS = {"trace_emitted", "trace_missing", "not_observed", "unknown_compact"}
REPORT_LABELS = {"written", "missing", "not_observed"}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_prompts?|raw_bfcl_case_content|raw_cases?|raw_commands?|raw_provider_requests?|raw_provider_responses?|raw_response_headers?|raw_logs?|raw_traces?|raw_model_output_text|raw_tool_args?|raw_result_trees?|endpoint_values?|key_values?|api_key_values?|secret_values?|scorer_diffs?|candidate_outputs?|provider_payload_value|prompt_text|case_content|trace_content|log_content|tool_argument_value|gold_value|reference_value|expected_value)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint value|key value|api key|provider payload|raw prompt|raw case|raw command|raw log|raw trace|raw model output|raw tool arg|raw result tree|scorer diff|candidate output|openrouter|gpt-4o"),
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
        if key and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "route_model" and value == "gpt-4.1":
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_proxy_preflight_failure_telemetry_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("measurement_kind") != "sanitized_bfcl_proxy_preflight_failure_telemetry":
        blockers.append(f"measurement_kind_invalid:{data.get('measurement_kind')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
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
    missing = [field for field in REQUIRED_COMPACT_FIELDS if field not in record]
    extra = [field for field in record if field not in REQUIRED_COMPACT_FIELDS]
    if missing:
        blockers.append(f"missing_required_fields:{missing!r}")
    if extra:
        blockers.append(f"extra_fields:{extra!r}")
    if record:
        if record.get("preflight_command_executed") is not True:
            blockers.append("preflight_command_executed_not_true")
        if record.get("preflight_exact_exit_code_class") not in EXIT_CODE_CLASSES:
            blockers.append(f"preflight_exact_exit_code_class_invalid:{record.get('preflight_exact_exit_code_class')!r}")
        if record.get("preflight_failed_check_label") not in FAILED_CHECK_LABELS:
            blockers.append(f"preflight_failed_check_label_invalid:{record.get('preflight_failed_check_label')!r}")
        if record.get("preflight_environment_check_label") not in ENV_LABELS:
            blockers.append(f"preflight_environment_check_label_invalid:{record.get('preflight_environment_check_label')!r}")
        if record.get("proxy_health_at_preflight_start") not in PROXY_HEALTH_LABELS:
            blockers.append(f"proxy_health_at_preflight_start_invalid:{record.get('proxy_health_at_preflight_start')!r}")
        if record.get("preflight_local_request_path_label") not in REQUEST_PATH_LABELS:
            blockers.append(f"preflight_local_request_path_label_invalid:{record.get('preflight_local_request_path_label')!r}")
        if record.get("preflight_http_status_class") not in HTTP_STATUS_LABELS:
            blockers.append(f"preflight_http_status_class_invalid:{record.get('preflight_http_status_class')!r}")
        if record.get("preflight_response_shape_label") not in RESPONSE_SHAPE_LABELS:
            blockers.append(f"preflight_response_shape_label_invalid:{record.get('preflight_response_shape_label')!r}")
        if record.get("preflight_timeout_or_exception_class") not in TIMEOUT_EXCEPTION_LABELS:
            blockers.append(f"preflight_timeout_or_exception_class_invalid:{record.get('preflight_timeout_or_exception_class')!r}")
        if record.get("preflight_trace_emission_label") not in TRACE_LABELS:
            blockers.append(f"preflight_trace_emission_label_invalid:{record.get('preflight_trace_emission_label')!r}")
        if record.get("preflight_report_written_label") not in REPORT_LABELS:
            blockers.append(f"preflight_report_written_label_invalid:{record.get('preflight_report_written_label')!r}")
        for key in ("provider_call_started", "bfcl_generate_started", "bfcl_evaluate_started", "scorer_started", "performance_evidence"):
            if record.get(key) is not False:
                blockers.append(f"{key}_not_false:{record.get(key)!r}")
        if record.get("candidate_specs_inert") is not True:
            blockers.append("candidate_specs_inert_not_true")
        if record.get("raw_outputs_removed") is not True:
            blockers.append("raw_outputs_removed_not_true")
        if not record.get("stop_gate_triggered"):
            blockers.append("stop_gate_triggered_missing")
        if not record.get("suspected_proxy_preflight_failure_stage"):
            blockers.append("suspected_proxy_preflight_failure_stage_missing")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) and data.get("records") else {}
    return {
        "report_scope": "bfcl_proxy_preflight_failure_telemetry_artifact_check",
        "artifact_path": str(path),
        "bfcl_proxy_preflight_failure_telemetry_artifact_passed": not blockers,
        "preflight_exact_exit_code_class": record.get("preflight_exact_exit_code_class") if isinstance(record, dict) else None,
        "provider_call_started": record.get("provider_call_started") if isinstance(record, dict) else None,
        "bfcl_generate_started": record.get("bfcl_generate_started") if isinstance(record, dict) else None,
        "stop_gate_triggered": record.get("stop_gate_triggered") if isinstance(record, dict) else None,
        "suspected_proxy_preflight_failure_stage": record.get("suspected_proxy_preflight_failure_stage") if isinstance(record, dict) else None,
        "raw_outputs_removed": record.get("raw_outputs_removed") if isinstance(record, dict) else None,
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
        summary = {"report_scope": "bfcl_proxy_preflight_failure_telemetry_artifact_check", "bfcl_proxy_preflight_failure_telemetry_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_proxy_preflight_failure_telemetry_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
