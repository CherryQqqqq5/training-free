#!/usr/bin/env python3
"""Check the prepared BFCL proxy response-parser debug packet."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_response_parser_debug_packet.json")
DEFAULT_OFFLINE_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_response_parser_offline_debug.json")

ALLOWED_OUTPUT_FIELDS = [
    "has_instructions",
    "instructions_preserved_to_chat_messages",
    "input_message_count",
    "tools_count",
    "tool_choice_shape",
    "raw_chat_has_tool_calls",
    "raw_chat_has_nonempty_text",
    "engine_final_has_tool_calls",
    "engine_final_content_empty",
    "engine_coerced_nonempty_text_to_empty",
    "responses_output_has_function_call",
    "responses_output_has_message_text",
    "bfcl_decode_execute_nonempty",
    "suspected_failure_stage",
]
DEBUG_QUESTIONS = [
    "responses_instructions_input_conversion_loss",
    "tool_choice_tools_conversion_loss",
    "engine_no_tool_text_to_empty_coercion",
    "chat_to_responses_payload_shape_loss",
    "bfcl_responses_parser_decode_mismatch",
]
REQUIRED_FALSE = (
    "authorized",
    "provider_request_authorized",
    "bfcl_smoke_authorized",
    "bfcl_full_eval_authorized",
    "bfcl_scorer_authorized",
    "candidate_generation_authorized",
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
    "raw_prompt_persistence_authorized",
    "raw_case_content_persistence_authorized",
    "raw_provider_payload_persistence_authorized",
    "raw_log_persistence_authorized",
    "raw_trace_persistence_authorized",
    "source_nonce_mapping_committed",
)
REQUIRED_TRUE = (
    "candidate_specs_inert",
    "endpoint_env_only",
    "api_key_env_only",
    "no_performance_evidence",
)
EXPECTED_FIELDS = {
    "approval_packet_kind": "bfcl_proxy_response_parser_debug",
    "approval_status": "prepared",
    "base_commit": "d665431cfa4163b77909cd64bdd8a4291b57a1f6",
    "provider_profile": "Chuangzhi/Novacode",
    "active_profile": "novacode",
    "route_model": "gpt-4.1",
    "old_signed_model": "gpt-5.2",
    "old_signed_model_status": "historical_superseded_inactive",
    "current_blocker": "repeated_empty_model_response_in_bfcl_responses_proxy_runtime_path",
    "offline_debug_artifact": str(DEFAULT_OFFLINE_ARTIFACT),
    "offline_debug_md_artifact": "outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_response_parser_offline_debug.md",
}
EXPECTED_STOPPED_SMOKE_FACTS = {
    "exact_8_ids_materialized": True,
    "run_id_count": 8,
    "stopped_on": "repeated_empty_model_response",
    "progress_observed": "6/8",
    "committed_smoke_artifacts": False,
    "committed_results": False,
    "performance_claim": False,
}
FORBIDDEN_TOKEN_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|https?://|provider_payload|provider response body|provider response header|raw prompt text|raw case content|gold/reference/expected|scorer diff|source nonce mapping)",
    re.IGNORECASE,
)
FORBIDDEN_ARTIFACT_KEYS = {
    "case_id",
    "prompt",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "provider_payload",
    "provider_response",
    "headers",
    "logs",
    "traces",
    "endpoint",
    "api_key",
    "candidate_output",
}
_ALLOWED_PACKET_TEXT_PATHS = {
    ("forbidden_material",),
    ("claim_policy",),
}


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


def _is_allowed_packet_text_path(path: tuple[str, ...]) -> bool:
    return bool(path and (path[0],) in _ALLOWED_PACKET_TEXT_PATHS)


def _scan_packet_text(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        if not isinstance(value, str) or _is_allowed_packet_text_path(path):
            continue
        if FORBIDDEN_TOKEN_RE.search(value):
            blockers.append(f"proxy_response_parser_packet_forbidden_literal:{'.'.join(path)}")
    return sorted(set(blockers))


def _scan_offline_artifact(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        data = load_json(path)
    except Exception as exc:  # pragma: no cover - surfaced through checker output
        return [f"proxy_response_parser_offline_artifact_load_failed:{exc}"]
    blockers: list[str] = []
    for value_path, value in _walk(data):
        if value_path and value_path[-1] in FORBIDDEN_ARTIFACT_KEYS:
            blockers.append(f"proxy_response_parser_offline_artifact_forbidden_key:{'.'.join(value_path)}")
        if isinstance(value, str) and FORBIDDEN_TOKEN_RE.search(value):
            blockers.append(f"proxy_response_parser_offline_artifact_forbidden_literal:{'.'.join(value_path)}")
    return sorted(set(blockers))


def validate(data: dict[str, Any], *, offline_artifact: Path = DEFAULT_OFFLINE_ARTIFACT) -> list[str]:
    blockers: list[str] = []
    for key, expected in EXPECTED_FIELDS.items():
        if data.get(key) != expected:
            blockers.append(f"proxy_response_parser_packet_{key}_invalid:{data.get(key)!r}")
    if data.get("allowed_output_fields") != ALLOWED_OUTPUT_FIELDS:
        blockers.append("proxy_response_parser_packet_allowed_output_fields_drift")
    if data.get("debug_questions") != DEBUG_QUESTIONS:
        blockers.append("proxy_response_parser_packet_debug_questions_drift")
    for key in REQUIRED_TRUE:
        if data.get(key) is not True:
            blockers.append(f"proxy_response_parser_packet_{key}_not_true:{data.get(key)!r}")
    for key in REQUIRED_FALSE:
        if data.get(key) is not False:
            blockers.append(f"proxy_response_parser_packet_{key}_not_false:{data.get(key)!r}")
    facts = data.get("stopped_smoke_facts") if isinstance(data.get("stopped_smoke_facts"), dict) else {}
    for key, expected in EXPECTED_STOPPED_SMOKE_FACTS.items():
        if facts.get(key) != expected:
            blockers.append(f"proxy_response_parser_packet_stopped_smoke_fact_{key}_invalid:{facts.get(key)!r}")
    claims = data.get("claim_policy") if isinstance(data.get("claim_policy"), dict) else {}
    for key in ("not_bfcl_smoke_retry", "not_full_default_baseline", "not_measurement_evidence", "not_performance_evidence", "not_3pp_claim", "not_huawei_readiness"):
        if claims.get(key) is not True:
            blockers.append(f"proxy_response_parser_packet_claim_{key}_not_true:{claims.get(key)!r}")
    blockers.extend(_scan_packet_text(data))
    blockers.extend(_scan_offline_artifact(offline_artifact))
    return blockers


def check(path: Path = DEFAULT_PACKET, *, offline_artifact: Path = DEFAULT_OFFLINE_ARTIFACT) -> dict[str, Any]:
    data = load_json(path)
    blockers = validate(data, offline_artifact=offline_artifact)
    return {
        "report_scope": "bfcl_proxy_response_parser_debug_packet_check",
        "packet_path": str(path),
        "offline_artifact_path": str(offline_artifact),
        "approval_status": data.get("approval_status"),
        "authorized": data.get("authorized"),
        "provider_request_authorized": data.get("provider_request_authorized"),
        "bfcl_smoke_authorized": data.get("bfcl_smoke_authorized"),
        "bfcl_scorer_authorized": data.get("bfcl_scorer_authorized"),
        "route_model": data.get("route_model"),
        "bfcl_proxy_response_parser_debug_packet_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--offline-artifact", type=Path, default=DEFAULT_OFFLINE_ARTIFACT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, offline_artifact=args.offline_artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "bfcl_proxy_response_parser_debug_packet_check",
            "packet_path": str(args.packet),
            "bfcl_proxy_response_parser_debug_packet_passed": False,
            "blockers": [f"proxy_response_parser_packet_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_proxy_response_parser_debug_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
