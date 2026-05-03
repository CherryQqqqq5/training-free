#!/usr/bin/env python3
"""Check compact live-provider preflight artifacts for raw leakage and scope drift."""

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

from scripts.check_bfcl_live_provider_preflight_gate import (
    REQUIRED_COMPACT_FIELDS,
    SIGNED_API_KEY_ENVS,
    SIGNED_BASE_URL_ENVS,
    SIGNED_ENDPOINT_ENVS,
)

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_provider_preflight_compact.json")
HTTP_STATUS_CLASSES = {"not_observed", "2xx", "3xx", "4xx", "5xx", "transport_error", "unknown"}
AUTH_LABELS = {"not_checked", "ok", "missing_endpoint_env", "missing_api_key_env", "endpoint_not_https", "auth_failed", "unknown"}
MODEL_LABELS = {"not_checked", "available", "unavailable", "unknown"}
ENDPOINT_MODE_LABELS = {"not_selected", "base_url", "full_endpoint"}
SELECTED_ENDPOINT_ENV_LABELS = set(SIGNED_BASE_URL_ENVS + SIGNED_ENDPOINT_ENVS + ["none"])
TRANSPORT_PATH_JOIN_LABELS = {"not_reached", "base_url_path_appended", "endpoint_used_as_is"}
CHECK_LABELS = {"not_checked", "passed", "failed", "missing_tool_call", "missing_text", "transport_error", "unknown"}
TRACE_LABELS = {"not_persisted_compact_only", "not_observed", "unknown"}
EXIT_CODE_CLASSES = {"zero", "nonzero_1", "nonzero_other", "not_executed"}
FAILED_CHECK_LABELS = {
    "none_observed",
    "packet_not_approved",
    "output_artifact_exists",
    "missing_endpoint_env",
    "missing_api_key_env",
    "endpoint_not_https",
    "provider_auth_failed",
    "provider_transport_error",
    "provider_non_2xx",
    "chat_tool_call",
    "responses_tool_call",
    "chat_text_response",
    "raw_or_secret_leak",
    "unknown",
}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_(requests?|responses?|bod(y|ies)|headers?|logs?|traces?|prompts?|cases?|tool_args?|provider_payloads?)|provider_payload|endpoint_values?|key_values?|api_key_values?|secret_values?|full_urls?|prompt_text|case_content|trace_content|log_content|tool_argument_value|gold_value|reference_value|expected_value|scorer_diffs?|candidate_outputs?|huawei_claim|performance_claim)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|api[_ -]?key|bearer |endpoint value|key value|full url|secret|provider payload|raw request|raw response|raw body|raw header|raw log|raw trace|raw prompt|raw case|raw tool arg|scorer diff|candidate output|huawei|\+3pp|performance evidence"),
    re.IGNORECASE,
)
ALLOWED_RAW_KEYS = {"raw_outputs_removed", "raw_outputs_committed"}


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
    if data.get("artifact_kind") != "bfcl_live_provider_preflight_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("measurement_kind") != "compact_synthetic_live_provider_preflight":
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
    missing = [field for field in REQUIRED_COMPACT_FIELDS if field not in record]
    if data.get("compact_schema_version") != "live_provider_preflight_endpoint_base_url_v2":
        legacy_optional = {"base_url_env_present", "endpoint_mode_label", "selected_endpoint_env_label", "transport_path_join_label"}
        missing = [field for field in missing if field not in legacy_optional]
    extra = [field for field in record if field not in REQUIRED_COMPACT_FIELDS]
    if missing:
        blockers.append(f"missing_required_fields:{missing!r}")
    if extra:
        blockers.append(f"extra_fields:{extra!r}")
    if record:
        require_transport_labels = data.get("compact_schema_version") == "live_provider_preflight_endpoint_base_url_v2"
        for key in ("preflight_command_executed", "provider_request_executed", "provider_call_started", "endpoint_env_present", "base_url_env_present", "api_key_env_present", "https_endpoint_valid"):
            if key == "base_url_env_present" and not require_transport_labels and key not in record:
                continue
            if record.get(key) not in (True, False):
                blockers.append(f"{key}_not_bool:{record.get(key)!r}")
        if record.get("http_status_class") not in HTTP_STATUS_CLASSES:
            blockers.append(f"http_status_class_invalid:{record.get('http_status_class')!r}")
        if record.get("auth_status_label") not in AUTH_LABELS:
            blockers.append(f"auth_status_label_invalid:{record.get('auth_status_label')!r}")
        if record.get("model_route_label") not in MODEL_LABELS:
            blockers.append(f"model_route_label_invalid:{record.get('model_route_label')!r}")
        if require_transport_labels or record.get("endpoint_mode_label") is not None:
            if record.get("endpoint_mode_label") not in ENDPOINT_MODE_LABELS:
                blockers.append(f"endpoint_mode_label_invalid:{record.get('endpoint_mode_label')!r}")
        if require_transport_labels or record.get("selected_endpoint_env_label") is not None:
            if record.get("selected_endpoint_env_label") not in SELECTED_ENDPOINT_ENV_LABELS:
                blockers.append(f"selected_endpoint_env_label_invalid:{record.get('selected_endpoint_env_label')!r}")
        if require_transport_labels or record.get("transport_path_join_label") is not None:
            if record.get("transport_path_join_label") not in TRANSPORT_PATH_JOIN_LABELS:
                blockers.append(f"transport_path_join_label_invalid:{record.get('transport_path_join_label')!r}")
        for key in ("chat_tool_call_label", "responses_tool_call_label", "chat_text_response_label"):
            if record.get(key) not in CHECK_LABELS:
                blockers.append(f"{key}_invalid:{record.get(key)!r}")
        if record.get("trace_emission_label") not in TRACE_LABELS:
            blockers.append(f"trace_emission_label_invalid:{record.get('trace_emission_label')!r}")
        if record.get("preflight_exact_exit_code_class") not in EXIT_CODE_CLASSES:
            blockers.append(f"preflight_exact_exit_code_class_invalid:{record.get('preflight_exact_exit_code_class')!r}")
        if record.get("preflight_failed_check_label") not in FAILED_CHECK_LABELS:
            blockers.append(f"preflight_failed_check_label_invalid:{record.get('preflight_failed_check_label')!r}")
        for key in ("bfcl_generate_started", "bfcl_evaluate_started", "scorer_started", "full_baseline_executed", "performance_evidence", "raw_outputs_committed"):
            if record.get(key) is not False:
                blockers.append(f"{key}_not_false:{record.get(key)!r}")
        if record.get("candidate_specs_inert") is not True:
            blockers.append(f"candidate_specs_inert_not_true:{record.get('candidate_specs_inert')!r}")
        if record.get("raw_outputs_removed") is not True:
            blockers.append(f"raw_outputs_removed_not_true:{record.get('raw_outputs_removed')!r}")
        if not record.get("stop_gate_triggered"):
            blockers.append("stop_gate_triggered_missing")
        if not record.get("suspected_live_preflight_failure_stage"):
            blockers.append("suspected_live_preflight_failure_stage_missing")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) and data.get("records") else {}
    return {
        "report_scope": "bfcl_live_provider_preflight_artifact_check",
        "artifact_path": str(path),
        "bfcl_live_provider_preflight_artifact_passed": not blockers,
        "provider_request_executed": record.get("provider_request_executed") if isinstance(record, dict) else None,
        "provider_call_started": record.get("provider_call_started") if isinstance(record, dict) else None,
        "http_status_class": record.get("http_status_class") if isinstance(record, dict) else None,
        "auth_status_label": record.get("auth_status_label") if isinstance(record, dict) else None,
        "bfcl_generate_started": record.get("bfcl_generate_started") if isinstance(record, dict) else None,
        "bfcl_evaluate_started": record.get("bfcl_evaluate_started") if isinstance(record, dict) else None,
        "scorer_started": record.get("scorer_started") if isinstance(record, dict) else None,
        "full_baseline_executed": record.get("full_baseline_executed") if isinstance(record, dict) else None,
        "performance_evidence": record.get("performance_evidence") if isinstance(record, dict) else None,
        "raw_outputs_removed": record.get("raw_outputs_removed") if isinstance(record, dict) else None,
        "raw_outputs_committed": record.get("raw_outputs_committed") if isinstance(record, dict) else None,
        "endpoint_mode_label": record.get("endpoint_mode_label") if isinstance(record, dict) else None,
        "selected_endpoint_env_label": record.get("selected_endpoint_env_label") if isinstance(record, dict) else None,
        "transport_path_join_label": record.get("transport_path_join_label") if isinstance(record, dict) else None,
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
        summary = {"report_scope": "bfcl_live_provider_preflight_artifact_check", "bfcl_live_provider_preflight_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_live_provider_preflight_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
