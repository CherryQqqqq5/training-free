#!/usr/bin/env python3
"""Check sanitized BFCL proxy/runtime adapter envelope shape diff artifacts."""

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

from scripts.check_bfcl_proxy_runtime_adapter_debug_packet import SIGNED_RUN_IDS_BY_CATEGORY

DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_runtime_adapter_envelope_shape_diff.json")
KEY_LITERAL_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
ENDPOINT_LITERAL_FRAGMENTS = ("http://", "https://")
FORBIDDEN_VALUE_FRAGMENTS = (
    "raw prompt text",
    "provider payload value",
    "provider response body value",
    "response header value",
    "raw trace path",
    "case content value",
    "case_id value",
    "gold value",
    "expected value",
    "reference value",
    "scorer diff value",
    "endpoint value",
    "key value",
    "nonce mapping value",
    "candidate output value",
)
REQUIRED_FALSE = (
    "provider_request_executed",
    "bfcl_smoke_executed",
    "bfcl_full_eval_executed",
    "scorer_executed",
    "source_input_read",
    "diagnostic_written",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "scorer_feedback_tuning_enabled",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "raw_request_persisted",
    "raw_response_persisted",
    "raw_header_persisted",
    "raw_body_persisted",
    "raw_log_persisted",
    "raw_trace_persisted",
    "raw_prompt_persisted",
    "raw_case_content_persisted",
    "endpoint_value_committed",
    "api_key_value_committed",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
)


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
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


def _secret_or_endpoint_blockers(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if any(fragment in lowered for fragment in ENDPOINT_LITERAL_FRAGMENTS):
            blockers.append(f"proxy_adapter_shape_diff_endpoint_literal_forbidden:{'.'.join(path)}")
        if KEY_LITERAL_PATTERN.search(value):
            blockers.append(f"proxy_adapter_shape_diff_key_literal_forbidden:{'.'.join(path)}")
        for fragment in FORBIDDEN_VALUE_FRAGMENTS:
            if fragment in lowered:
                blockers.append(f"proxy_adapter_shape_diff_forbidden_value_fragment:{fragment}")
    return sorted(set(blockers))


def _flatten_run_ids(by_category: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for values in by_category.values():
        if isinstance(values, list):
            ids.extend(str(value) for value in values)
    return ids


def validate(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = {
        "artifact_kind": "bfcl_proxy_runtime_adapter_envelope_shape_diff",
        "approval_status": "prepared",
        "provider_profile": "Chuangzhi/Novacode",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "shape_diff_high_level_conclusion": "synthetic_provider_contract_passed_but_bfcl_proxy_runtime_adapter_envelope_requires_review_before_retry",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"proxy_adapter_shape_diff_{key}_invalid:{data.get(key)!r}")
    for key in REQUIRED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"proxy_adapter_shape_diff_{key}_not_false:{data.get(key)!r}")
    if data.get("shape_fields_only") is not True:
        blockers.append(f"proxy_adapter_shape_diff_shape_fields_only_not_true:{data.get('shape_fields_only')!r}")
    if data.get("bfcl_proxy_runtime_adapter_shape_diff_passed") is not True:
        blockers.append(f"proxy_adapter_shape_diff_not_passed:{data.get('blockers')!r}")
    if data.get("blockers") not in ([], None):
        blockers.append("proxy_adapter_shape_diff_blockers_not_empty")
    refs = data.get("reviewed_run_id_references") if isinstance(data.get("reviewed_run_id_references"), dict) else {}
    if refs != SIGNED_RUN_IDS_BY_CATEGORY:
        blockers.append("proxy_adapter_shape_diff_reviewed_run_ids_drift")
    flat = _flatten_run_ids(refs)
    if len(flat) != 8:
        blockers.append(f"proxy_adapter_shape_diff_run_id_count_invalid:{len(flat)}")
    if len(flat) > 8:
        blockers.append(f"proxy_adapter_shape_diff_run_id_count_exceeds_8:{len(flat)}")
    if len(set(flat)) != len(flat):
        blockers.append("proxy_adapter_shape_diff_duplicate_run_ids")
    facts = data.get("stopped_smoke_facts") if isinstance(data.get("stopped_smoke_facts"), dict) else {}
    if facts.get("stopped_on") != "repeated_empty_model_response" or facts.get("progress_observed") != "6/8":
        blockers.append("proxy_adapter_shape_diff_stopped_smoke_facts_invalid")
    synthetic = data.get("successful_synthetic_provider_contract_shape") if isinstance(data.get("successful_synthetic_provider_contract_shape"), dict) else {}
    proxy = data.get("bfcl_proxy_runtime_planned_shape") if isinstance(data.get("bfcl_proxy_runtime_planned_shape"), dict) else {}
    if synthetic.get("route_model") != "gpt-4.1" or proxy.get("route_model") != "gpt-4.1":
        blockers.append("proxy_adapter_shape_diff_route_model_drift")
    if synthetic.get("tools_count") != 1:
        blockers.append(f"proxy_adapter_shape_diff_synthetic_tools_count_invalid:{synthetic.get('tools_count')!r}")
    if proxy.get("tool_choice_mode") != "required_string":
        blockers.append(f"proxy_adapter_shape_diff_proxy_tool_choice_mode_invalid:{proxy.get('tool_choice_mode')!r}")
    for shape_name, shape in [("synthetic", synthetic), ("proxy", proxy)]:
        if not isinstance(shape.get("request_top_level_keys"), list):
            blockers.append(f"proxy_adapter_shape_diff_{shape_name}_top_level_keys_missing")
        if not isinstance(shape.get("parser_expected_response_keys"), list) or "tool_calls" not in shape.get("parser_expected_response_keys", []):
            blockers.append(f"proxy_adapter_shape_diff_{shape_name}_parser_expected_tool_calls_missing")
        flags = shape.get("tool_schema_structural_flags") if isinstance(shape.get("tool_schema_structural_flags"), dict) else {}
        if flags.get("function_tool") is not True:
            blockers.append(f"proxy_adapter_shape_diff_{shape_name}_function_tool_not_true:{flags.get('function_tool')!r}")
        if not isinstance(shape.get("tool_schema_structural_hash"), str) or len(shape.get("tool_schema_structural_hash", "")) != 16:
            blockers.append(f"proxy_adapter_shape_diff_{shape_name}_tool_schema_hash_invalid")
    blockers.extend(_secret_or_endpoint_blockers(data))
    return blockers


def check(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    data = load_json(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_proxy_runtime_adapter_shape_diff_check",
        "artifact_path": str(path),
        "route_model": data.get("route_model"),
        "shape_fields_only": data.get("shape_fields_only"),
        "shape_diff_high_level_conclusion": data.get("shape_diff_high_level_conclusion"),
        "bfcl_proxy_runtime_adapter_shape_diff_passed": not blockers,
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
        summary = {
            "report_scope": "bfcl_proxy_runtime_adapter_shape_diff_check",
            "artifact_path": str(args.artifact),
            "bfcl_proxy_runtime_adapter_shape_diff_passed": False,
            "blockers": [f"proxy_adapter_shape_diff_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_proxy_runtime_adapter_shape_diff_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
