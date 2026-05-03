#!/usr/bin/env python3
"""Check compact proxy-vs-direct upstream shape-diff artifacts."""

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

from scripts.check_bfcl_proxy_vs_direct_upstream_shape_diff_gate import REQUIRED_COMPACT_FIELDS

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_vs_direct_upstream_shape_diff_compact.json")
API_KEY_ENV_LABELS = {"CHUANGZHI_API_KEY", "NOVACODE_API_KEY", "OPENAI_API_KEY", "unknown", "none"}
BASE_URL_ENV_LABELS = {"GRC_UPSTREAM_BASE_URL", "NOVACODE_BASE_URL", "unknown", "none"}
MATCH_LABELS = {"match", "mismatch", "unknown"}
MODEL_LABELS = {"match_gpt_4_1", "mismatch", "unknown"}
TOOL_CHOICE_LABELS = {"function_object_aligned", "direct_function_proxy_other", "missing", "unknown"}
TOOLS_SHAPE_LABELS = {"chat_function_tools_aligned", "mismatch", "unknown"}
MESSAGES_SHAPE_LABELS = {"direct_user_only_proxy_system_developer_user", "direct_user_only_proxy_developer_user", "aligned", "unknown"}
TOKEN_FIELD_LABELS = {"max_tokens_aligned", "direct_max_tokens_proxy_max_output_tokens", "mismatch", "unknown"}
RUNTIME_PATCH_LABELS = {"nonzero_runtime_request_patch", "zero_runtime_request_patch", "unknown"}
MISMATCH_LABELS = {"api_key_env_mismatch", "base_url_env_mismatch", "payload_shape_drift", "none_observed", "unknown"}
FAILED_CHECK_LABELS = {"none_observed", "packet_not_approved", "output_artifact_exists", "raw_or_secret_leak", "unknown"}
FORBIDDEN_KEY_RE = re.compile(
    r"(^|_)(raw_(requests?|responses?|bod(y|ies)|contents?|headers?|logs?|traces?|prompts?|cases?|tool_args?|provider_payloads?)|provider_payload|endpoint_values?|key_values?|api_key_values?|secret_values?|full_urls?|prompt_text|case_content|trace_content|log_content|tool_argument_value|gold_value|reference_value|expected_value|scorer_diffs?|candidate_outputs?|huawei_claim|performance_claim|headers?)(_|$)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|bearer |endpoint value|key value|full url|secret|provider payload|raw request|raw response|raw body|raw content|raw header|raw log|raw trace|raw prompt|raw case|raw tool arg|scorer diff|candidate output|huawei|\+3pp|performance evidence"),
    re.IGNORECASE,
)
ALLOWED_ENV_LABEL_KEYS = {
    "direct_selected_api_key_env_label",
    "proxy_selected_api_key_env_label",
    "direct_selected_base_url_env_label",
    "proxy_selected_base_url_env_label",
}


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
        if key and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{dotted}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if key == "route_model" and value == "gpt-4.1":
                continue
            blockers.append(f"forbidden_value:{dotted}")
    return sorted(set(blockers))


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_proxy_vs_direct_upstream_shape_diff_compact":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("compact_schema_version") != "proxy_vs_direct_upstream_shape_diff_v1":
        blockers.append(f"compact_schema_version_invalid:{data.get('compact_schema_version')!r}")
    if data.get("measurement_kind") != "compact_static_proxy_vs_direct_upstream_shape_diff":
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
            "api_key_env_match",
            "base_url_env_match",
            "model_label_match",
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
        ):
            if record.get(key) not in (True, False):
                blockers.append(f"{key}_not_bool:{record.get(key)!r}")
        if record.get("direct_selected_api_key_env_label") not in API_KEY_ENV_LABELS:
            blockers.append(f"direct_selected_api_key_env_label_invalid:{record.get('direct_selected_api_key_env_label')!r}")
        if record.get("proxy_selected_api_key_env_label") not in API_KEY_ENV_LABELS:
            blockers.append(f"proxy_selected_api_key_env_label_invalid:{record.get('proxy_selected_api_key_env_label')!r}")
        if record.get("direct_selected_base_url_env_label") not in BASE_URL_ENV_LABELS:
            blockers.append(f"direct_selected_base_url_env_label_invalid:{record.get('direct_selected_base_url_env_label')!r}")
        if record.get("proxy_selected_base_url_env_label") not in BASE_URL_ENV_LABELS:
            blockers.append(f"proxy_selected_base_url_env_label_invalid:{record.get('proxy_selected_base_url_env_label')!r}")
        if record.get("tool_choice_shape_label") not in TOOL_CHOICE_LABELS:
            blockers.append(f"tool_choice_shape_label_invalid:{record.get('tool_choice_shape_label')!r}")
        if record.get("tools_shape_label") not in TOOLS_SHAPE_LABELS:
            blockers.append(f"tools_shape_label_invalid:{record.get('tools_shape_label')!r}")
        if record.get("messages_shape_label") not in MESSAGES_SHAPE_LABELS:
            blockers.append(f"messages_shape_label_invalid:{record.get('messages_shape_label')!r}")
        if record.get("token_field_shape_label") not in TOKEN_FIELD_LABELS:
            blockers.append(f"token_field_shape_label_invalid:{record.get('token_field_shape_label')!r}")
        if record.get("runtime_patch_label") not in RUNTIME_PATCH_LABELS:
            blockers.append(f"runtime_patch_label_invalid:{record.get('runtime_patch_label')!r}")
        if record.get("suspected_mismatch_label") not in MISMATCH_LABELS:
            blockers.append(f"suspected_mismatch_label_invalid:{record.get('suspected_mismatch_label')!r}")
        if record.get("preflight_failed_check_label") not in FAILED_CHECK_LABELS:
            blockers.append(f"preflight_failed_check_label_invalid:{record.get('preflight_failed_check_label')!r}")
        for key in ("provider_call_started", "proxy_live_request_started", "profile_sourced", "bfcl_generate_started", "bfcl_evaluate_started", "scorer_started", "full_baseline_executed", "source_collection_executed", "source_diagnostics_executed", "performance_evidence", "raw_outputs_committed"):
            if record.get(key) is not False:
                blockers.append(f"{key}_not_false:{record.get(key)!r}")
        if record.get("candidate_specs_inert") is not True:
            blockers.append(f"candidate_specs_inert_not_true:{record.get('candidate_specs_inert')!r}")
        if not record.get("stop_gate_triggered"):
            blockers.append("stop_gate_triggered_missing")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = _load(path)
    blockers = validate(data)
    record = data.get("records", [{}])[0] if isinstance(data.get("records"), list) and data.get("records") else {}
    return {
        "report_scope": "bfcl_proxy_vs_direct_upstream_shape_diff_artifact_check",
        "artifact_path": str(path),
        "bfcl_proxy_vs_direct_upstream_shape_diff_artifact_passed": not blockers,
        "direct_selected_api_key_env_label": record.get("direct_selected_api_key_env_label") if isinstance(record, dict) else None,
        "proxy_selected_api_key_env_label": record.get("proxy_selected_api_key_env_label") if isinstance(record, dict) else None,
        "api_key_env_match": record.get("api_key_env_match") if isinstance(record, dict) else None,
        "direct_selected_base_url_env_label": record.get("direct_selected_base_url_env_label") if isinstance(record, dict) else None,
        "proxy_selected_base_url_env_label": record.get("proxy_selected_base_url_env_label") if isinstance(record, dict) else None,
        "base_url_env_match": record.get("base_url_env_match") if isinstance(record, dict) else None,
        "tool_choice_shape_label": record.get("tool_choice_shape_label") if isinstance(record, dict) else None,
        "tools_shape_label": record.get("tools_shape_label") if isinstance(record, dict) else None,
        "messages_shape_label": record.get("messages_shape_label") if isinstance(record, dict) else None,
        "token_field_shape_label": record.get("token_field_shape_label") if isinstance(record, dict) else None,
        "runtime_patch_label": record.get("runtime_patch_label") if isinstance(record, dict) else None,
        "suspected_mismatch_label": record.get("suspected_mismatch_label") if isinstance(record, dict) else None,
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
        summary = {"report_scope": "bfcl_proxy_vs_direct_upstream_shape_diff_artifact_check", "bfcl_proxy_vs_direct_upstream_shape_diff_artifact_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_proxy_vs_direct_upstream_shape_diff_artifact_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
