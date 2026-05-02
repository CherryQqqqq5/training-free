#!/usr/bin/env python3
"""Check the prepared BFCL proxy/runtime adapter debug packet."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_runtime_adapter_debug_packet.json")
SIGNED_RUN_IDS_BY_CATEGORY = {
    "web_search_base": ["web_search_base_0"],
    "memory_kv": ["memory_kv_0-customer-0"],
    "multi_turn_base": ["multi_turn_base_0"],
    "multi_turn_long_context": ["multi_turn_long_context_0"],
    "multi_turn_miss_param": ["multi_turn_miss_param_0"],
    "multi_turn_miss_func": ["multi_turn_miss_func_0"],
    "irrelevance": ["irrelevance_0"],
    "live_irrelevance": ["live_irrelevance_0-0-0"],
}
ALLOWED_SHAPE_DIFF_FIELDS = [
    "route_model",
    "request_top_level_keys",
    "message_count",
    "role_sequence",
    "content_length_buckets",
    "tools_count",
    "tool_schema_structural_flags",
    "tool_schema_structural_hash",
    "tool_choice_mode",
    "token_field_presence",
    "temperature_presence",
    "timeout_streaming_flags",
    "parser_expected_response_keys",
    "reviewed_run_id_references",
    "empty_response_handling_path_labels",
]
KEY_LITERAL_PATTERN = re.compile(r"sk-[A-Za-z0-9_-]{16,}")
ENDPOINT_LITERAL_FRAGMENTS = ("http://", "https://")
REQUIRED_FALSE = (
    "authorized",
    "proxy_runtime_adapter_debug_execution_authorized",
    "provider_request_authorized",
    "bfcl_smoke_authorized",
    "bfcl_full_eval_authorized",
    "bfcl_scorer_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "scorer_feedback_tuning_enabled",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "openrouter_allowed",
    "endpoint_value_committed",
    "api_key_value_committed",
    "raw_request_persistence_authorized",
    "raw_response_persistence_authorized",
    "raw_header_persistence_authorized",
    "raw_body_persistence_authorized",
    "raw_log_persistence_authorized",
    "raw_trace_persistence_authorized",
    "raw_prompt_persistence_authorized",
    "raw_case_content_persistence_authorized",
    "source_nonce_mapping_committed",
)
REQUIRED_TRUE = (
    "proxy_runtime_adapter_debug_preparation_authorized",
    "candidate_specs_inert",
    "endpoint_env_only",
    "api_key_env_only",
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
        if path and path[0] in {"forbidden_material", "claim_policy"}:
            continue
        lowered = value.lower()
        if any(fragment in lowered for fragment in ENDPOINT_LITERAL_FRAGMENTS):
            blockers.append(f"proxy_adapter_debug_packet_endpoint_literal_forbidden:{'.'.join(path)}")
        if KEY_LITERAL_PATTERN.search(value):
            blockers.append(f"proxy_adapter_debug_packet_key_literal_forbidden:{'.'.join(path)}")
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
        "approval_packet_kind": "bfcl_proxy_runtime_adapter_debug",
        "approval_status": "prepared",
        "provider_profile": "Chuangzhi/Novacode",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "old_signed_model": "gpt-5.2",
        "old_signed_model_status": "historical_superseded_inactive",
        "precondition_commit": "63821dabc081635ddea39afa81af0229550a48fd",
        "protocol_debug_artifact": "outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_provider_protocol_debug_compact.json",
        "smoke_run_id_manifest": "outputs/artifacts/stage1_bfcl_acceptance/bfcl_stage1_smoke_run_id_manifest.json",
        "shape_diff_artifact": "outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_runtime_adapter_envelope_shape_diff.json",
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"proxy_adapter_debug_packet_{key}_invalid:{data.get(key)!r}")
    for key in REQUIRED_TRUE:
        if data.get(key) is not True:
            blockers.append(f"proxy_adapter_debug_packet_{key}_not_true:{data.get(key)!r}")
    for key in REQUIRED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"proxy_adapter_debug_packet_{key}_not_false:{data.get(key)!r}")
    if data.get("allowed_shape_diff_fields") != ALLOWED_SHAPE_DIFF_FIELDS:
        blockers.append("proxy_adapter_debug_packet_allowed_shape_diff_fields_drift")
    run_ids = data.get("reviewed_run_ids_by_category") if isinstance(data.get("reviewed_run_ids_by_category"), dict) else {}
    if run_ids != SIGNED_RUN_IDS_BY_CATEGORY:
        blockers.append("proxy_adapter_debug_packet_reviewed_run_ids_drift")
    flat = _flatten_run_ids(run_ids)
    if len(flat) != 8:
        blockers.append(f"proxy_adapter_debug_packet_run_id_count_invalid:{len(flat)}")
    if len(flat) > 8:
        blockers.append(f"proxy_adapter_debug_packet_run_id_count_exceeds_8:{len(flat)}")
    if len(set(flat)) != len(flat):
        blockers.append("proxy_adapter_debug_packet_duplicate_run_ids")
    facts = data.get("stopped_smoke_facts") if isinstance(data.get("stopped_smoke_facts"), dict) else {}
    expected_facts = {
        "exact_8_ids_materialized": True,
        "run_id_count": 8,
        "stopped_on": "repeated_empty_model_response",
        "progress_observed": "6/8",
        "committed_smoke_artifacts": False,
        "committed_results": False,
        "performance_claim": False,
    }
    for key, value in expected_facts.items():
        if facts.get(key) != value:
            blockers.append(f"proxy_adapter_debug_packet_stopped_smoke_fact_{key}_invalid:{facts.get(key)!r}")
    claims = data.get("claim_policy") if isinstance(data.get("claim_policy"), dict) else {}
    for key in ["not_bfcl_smoke_retry", "not_full_default_baseline", "not_measurement_evidence", "not_performance_evidence", "not_3pp_claim", "not_huawei_readiness"]:
        if claims.get(key) is not True:
            blockers.append(f"proxy_adapter_debug_packet_claim_{key}_not_true:{claims.get(key)!r}")
    forbidden = data.get("forbidden_material") if isinstance(data.get("forbidden_material"), list) else []
    for required in [
        "raw prompt",
        "provider payload",
        "provider response body",
        "provider response header",
        "raw log",
        "raw trace",
        "raw case content",
        "case_id",
        "gold/reference/expected",
        "scorer diff",
        "endpoint/key value",
        "source nonce mapping",
        "candidate output",
    ]:
        if required not in forbidden:
            blockers.append(f"proxy_adapter_debug_packet_forbidden_material_missing:{required}")
    blockers.extend(_secret_or_endpoint_blockers(data))
    return blockers


def check(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    data = load_json(path)
    blockers = validate(data)
    return {
        "report_scope": "bfcl_proxy_runtime_adapter_debug_packet_check",
        "packet_path": str(path),
        "approval_status": data.get("approval_status"),
        "route_model": data.get("route_model"),
        "active_profile": data.get("active_profile"),
        "provider_request_authorized": data.get("provider_request_authorized"),
        "bfcl_smoke_authorized": data.get("bfcl_smoke_authorized"),
        "bfcl_proxy_runtime_adapter_debug_packet_passed": not blockers,
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
        summary = {
            "report_scope": "bfcl_proxy_runtime_adapter_debug_packet_check",
            "packet_path": str(args.packet),
            "bfcl_proxy_runtime_adapter_debug_packet_passed": False,
            "blockers": [f"proxy_adapter_debug_packet_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_proxy_runtime_adapter_debug_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
