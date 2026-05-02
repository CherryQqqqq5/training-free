#!/usr/bin/env python3
"""Build shape-only BFCL runner/request delta evidence without provider execution."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from grc.runtime.proxy import (  # noqa: E402
    _responses_input_to_messages,
    _responses_token_fields_to_chat_fields,
    _responses_tools_to_chat_tools,
)

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_runner_request_shape_delta_packet.json")
DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_runner_request_shape_delta.json")
DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_runner_request_shape_delta.md")
TELEMETRY_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_shape_telemetry_compact.json")
SMOKE_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_stage1_smoke_run_id_manifest.json")
RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
BFCL_ENV = Path("configs/bfcl_v4_phase1.env")
RUNNER = Path("scripts/run_bfcl_v4_baseline.sh")

FALSE_FLAGS = (
    "provider_request_executed",
    "bfcl_smoke_executed",
    "scorer_executed",
    "full_baseline_executed",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "raw_prompt_persisted",
    "raw_case_content_persisted",
    "raw_provider_payload_persisted",
    "raw_log_persisted",
    "raw_trace_persisted",
    "endpoint_or_key_committed",
)

SUSPECTED_GAP_PRIORITY = [
    "bfcl_handler_missing_tool_choice_vs_telemetry_function_object",
    "bfcl_handler_missing_token_limit_vs_telemetry_max_output_tokens",
    "bfcl_exact_id_payload_shape_not_exercised_by_synthetic_telemetry",
    "bfcl_multiturn_history_shape_not_exercised_by_synthetic_telemetry",
    "bfcl_runner_proxy_invocation_mode_differs_from_telemetry_client_factory",
]


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain object")
    return data


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _bucket(value: int) -> str:
    if value == 0:
        return "zero"
    if value == 1:
        return "one"
    if value == 2:
        return "two"
    if value <= 8:
        return "small"
    return "many"


def _role_sequence(messages: list[dict[str, Any]]) -> list[str]:
    return [str(message.get("role", "unknown")) for message in messages if isinstance(message, dict)]


def _item_type_sequence(items: Any) -> list[str]:
    if not isinstance(items, list):
        return ["unknown"]
    sequence = []
    for item in items:
        if isinstance(item, dict):
            sequence.append(str(item.get("type") or item.get("role") or "object"))
        else:
            sequence.append(type(item).__name__)
    return sequence


def _shape(value: Any) -> str:
    if isinstance(value, dict) and value.get("type") == "function":
        return "function_object"
    if isinstance(value, str):
        return f"{value}_string"
    if value is None:
        return "absent"
    return type(value).__name__


def _token_shape(payload: dict[str, Any]) -> dict[str, str]:
    return {
        "max_output_tokens": "present" if "max_output_tokens" in payload else "missing",
        "max_tokens": "present" if "max_tokens" in payload else "missing",
        "max_completion_tokens": "present" if "max_completion_tokens" in payload else "missing",
    }


def _runtime_policy_shape() -> dict[str, Any]:
    cfg = _load_yaml(RUNTIME_CONFIG)
    policy = cfg.get("runtime_policy") if isinstance(cfg.get("runtime_policy"), dict) else {}
    coercion = policy.get("coerce_no_tool_response_to_empty_kinds")
    record_only = policy.get("record_only_no_tool_kinds")
    return {
        "text_to_empty_coercion_enabled": bool(coercion),
        "text_to_empty_coercion_kind_count": len(coercion) if isinstance(coercion, list) else 0,
        "record_only_no_tool_kind_count": len(record_only) if isinstance(record_only, list) else 0,
        "exact_next_tool_choice_mode": str(policy.get("exact_next_tool_choice_mode") or "absent"),
        "scorer_feedback_enabled": bool(policy.get("scorer_feedback_enabled")),
        "scorer_feedback_status": str(policy.get("scorer_feedback_status") or "absent"),
    }


def _bfcl_model_alias() -> str:
    text = BFCL_ENV.read_text(encoding="utf-8")
    marker = 'export GRC_BFCL_MODEL="${GRC_BFCL_MODEL:-'
    if marker in text:
        return text.split(marker, 1)[1].split('}"', 1)[0]
    return "unknown"


def _bfcl_handler_shape() -> dict[str, Any]:
    alias = _bfcl_model_alias()
    handler_label = "unknown"
    model_style = "unknown"
    api_kwargs = {
        "input": "present",
        "model": "present",
        "store": "present_false",
        "temperature": "present",
        "tools": "present_when_tools_nonempty",
        "tool_choice": "missing",
        "max_output_tokens": "missing",
        "max_tokens": "missing",
        "stream": "missing",
        "timeout": "sdk_default_or_client_config",
        "response_format": "missing",
        "parallel_tool_calls": "missing",
    }
    try:
        from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING
        config = MODEL_CONFIG_MAPPING.get(alias)
        handler = getattr(config, "model_handler", None) if config is not None else None
        handler_label = getattr(handler, "__name__", "unknown")
        model_style = "openai_responses" if handler_label == "OpenAIResponsesHandler" else "unknown"
    except Exception:
        handler_label = "import_unavailable"
        model_style = "import_unavailable"
    return {
        "bfcl_model_alias": alias,
        "handler_class_label": handler_label,
        "api_path_label": "responses" if handler_label == "OpenAIResponsesHandler" else "unknown",
        "model_style_label": model_style,
        "api_kwargs_shape": api_kwargs,
        "decode_extraction_path_label": "OpenAIResponsesHandler._parse_query_response_FC_then_decode_execute" if handler_label == "OpenAIResponsesHandler" else "unknown",
    }


def _telemetry_shape() -> dict[str, Any]:
    artifact = _load_json(TELEMETRY_ARTIFACT)
    records = artifact.get("records") if isinstance(artifact.get("records"), list) else []
    first = records[0] if records and isinstance(records[0], dict) else {}
    synthetic_request = {
        "model": artifact.get("route_model"),
        "instructions": "redacted_shape_only",
        "input": [{"role": "user", "content": "redacted_shape_only"}],
        "tools": [{"type": "function", "name": "redacted", "parameters": {"type": "object", "additionalProperties": False}}],
        "tool_choice": {"type": "function", "function": {"name": "redacted"}},
        "max_output_tokens": 32,
    }
    chat_messages = _responses_input_to_messages(synthetic_request["input"], instructions=synthetic_request["instructions"])
    chat_payload = {
        "messages": chat_messages,
        **_responses_token_fields_to_chat_fields(synthetic_request),
        "tools": _responses_tools_to_chat_tools(synthetic_request["tools"]),
        "tool_choice": synthetic_request["tool_choice"],
    }
    return {
        "source_artifact": str(TELEMETRY_ARTIFACT),
        "request_path_label": first.get("endpoint_path_label", "responses_to_chat_proxy"),
        "handler_class_label": "signed_live_shape_telemetry_client",
        "api_path_label": "responses_to_chat_proxy_then_chat_completions",
        "input_role_sequence": _role_sequence(chat_messages),
        "input_item_type_sequence": _item_type_sequence(synthetic_request["input"]),
        "message_count_bucket": _bucket(len(chat_messages)),
        "content_item_type_counts": {"redacted_text_items": 2},
        "function_call_history_count": 0,
        "function_call_output_history_count": 0,
        "instructions_or_developer_present": bool(chat_messages and chat_messages[0].get("role") in {"system", "developer"}),
        "tools_count": len(chat_payload.get("tools") or []),
        "tool_schema_shape": "single_function_additionalProperties_false",
        "tool_choice_shape": _shape(chat_payload.get("tool_choice")),
        "tool_choice_value_class": "function_object_redacted_name",
        "model_route": artifact.get("route_model"),
        "provider_profile": artifact.get("active_profile"),
        "token_fields": _token_shape(synthetic_request),
        "token_forwarded_label": first.get("token_forwarding_label", "unknown"),
        "stream_flag": "missing_non_streaming",
        "timeout_bucket": "transport_default_30s",
        "temperature_presence": "present_zero",
        "top_p_presence": "missing",
        "response_format_presence": "missing",
        "parallel_tool_calls_presence": "missing",
        "proxy_endpoint_path_used": "responses_to_chat_proxy",
        "decode_extraction_path_label": first.get("parser_decode_path_label", "unknown"),
    }


def _runner_shape() -> dict[str, Any]:
    manifest = _load_json(SMOKE_MANIFEST)
    mappings = manifest.get("source_category_mappings") if isinstance(manifest.get("source_category_mappings"), list) else []
    categories = [str(row.get("bfcl_category")) for row in mappings if isinstance(row, dict)]
    run_ids = []
    for value in (manifest.get("run_ids_by_category") or {}).values():
        if isinstance(value, list):
            run_ids.extend(str(item) for item in value)
    multi_turn_count = sum(1 for category in categories if category.startswith("multi_turn"))
    handler = _bfcl_handler_shape()
    runtime_policy = _runtime_policy_shape()
    return {
        "source_manifest": str(SMOKE_MANIFEST),
        "request_path_label": "bfcl_runner_generate_to_local_grc_proxy",
        "handler_class_label": handler["handler_class_label"],
        "api_path_label": handler["api_path_label"],
        "input_role_sequence": ["developer_or_user_redacted", "user_redacted", "history_if_multiturn_redacted"],
        "input_item_type_sequence": ["message", "function_call_history_possible", "function_call_output_history_possible"],
        "message_count_bucket": "varies_by_exact_id",
        "content_item_type_counts": {"redacted_text_items": "varies", "redacted_tool_history_items": "varies"},
        "function_call_history_count": "possible_nonzero_for_multiturn",
        "function_call_output_history_count": "possible_nonzero_for_multiturn",
        "exact_id_count": len(run_ids),
        "category_count": len(categories),
        "multi_turn_category_count": multi_turn_count,
        "instructions_or_developer_present": "handler_substitutes_system_to_developer_when_present",
        "tools_count": "per_case_function_count_redacted_nonzero_expected",
        "tool_schema_shape": "bfcl_converted_openapi_tools_shape_redacted",
        "tool_choice_shape": "absent",
        "tool_choice_value_class": "missing_in_OpenAIResponsesHandler_query_kwargs",
        "model_route": "gpt-4.1",
        "provider_profile": "novacode",
        "bfcl_model_alias": handler["bfcl_model_alias"],
        "token_fields": {"max_output_tokens": handler["api_kwargs_shape"]["max_output_tokens"], "max_tokens": handler["api_kwargs_shape"]["max_tokens"], "max_completion_tokens": "missing"},
        "token_forwarded_label": "no_explicit_token_limit_in_bfcl_handler_kwargs",
        "stream_flag": handler["api_kwargs_shape"]["stream"],
        "timeout_bucket": "proxy_timeout_120s_runtime_config_and_sdk_default_client_timeout",
        "temperature_presence": handler["api_kwargs_shape"]["temperature"],
        "top_p_presence": "missing",
        "response_format_presence": handler["api_kwargs_shape"]["response_format"],
        "parallel_tool_calls_presence": handler["api_kwargs_shape"]["parallel_tool_calls"],
        "store_presence": handler["api_kwargs_shape"]["store"],
        "proxy_endpoint_path_used": "local_proxy_v1_responses",
        "decode_extraction_path_label": handler["decode_extraction_path_label"],
        "runtime_config_policy_flags": runtime_policy,
        "runner_invocation_mode": {
            "use_run_ids_env": "GRC_BFCL_USE_RUN_IDS=1 required for smoke",
            "partial_eval_env": "GRC_BFCL_PARTIAL_EVAL=1 used for smoke retry",
            "num_threads_env": "GRC_BFCL_NUM_THREADS=1",
            "local_proxy_base_url": "loopback_proxy_v1_redacted",
        },
    }


def detect_suspected_gaps(telemetry: dict[str, Any], runner: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    if runner.get("tool_choice_shape") != telemetry.get("tool_choice_shape"):
        gaps.append("bfcl_handler_missing_tool_choice_vs_telemetry_function_object")
    runner_tokens = runner.get("token_fields", {}) if isinstance(runner.get("token_fields"), dict) else {}
    telemetry_tokens = telemetry.get("token_fields", {}) if isinstance(telemetry.get("token_fields"), dict) else {}
    if runner_tokens.get("max_output_tokens") != telemetry_tokens.get("max_output_tokens"):
        gaps.append("bfcl_handler_missing_token_limit_vs_telemetry_max_output_tokens")
    if runner.get("exact_id_count") and runner.get("exact_id_count") != 2:
        gaps.append("bfcl_exact_id_payload_shape_not_exercised_by_synthetic_telemetry")
    if runner.get("multi_turn_category_count", 0) and runner.get("function_call_history_count") != telemetry.get("function_call_history_count"):
        gaps.append("bfcl_multiturn_history_shape_not_exercised_by_synthetic_telemetry")
    if runner.get("request_path_label") != telemetry.get("request_path_label"):
        gaps.append("bfcl_runner_proxy_invocation_mode_differs_from_telemetry_client_factory")
    return [gap for gap in SUSPECTED_GAP_PRIORITY if gap in gaps]


def build_report() -> dict[str, Any]:
    telemetry = _telemetry_shape()
    runner = _runner_shape()
    suspected = detect_suspected_gaps(telemetry, runner)
    report = {
        "artifact_kind": "bfcl_runner_request_shape_delta",
        "approval_status": "prepared",
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "provider_request_executed": False,
        "bfcl_smoke_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_prompt_persisted": False,
        "raw_case_content_persisted": False,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "endpoint_or_key_committed": False,
        "telemetry_shape": telemetry,
        "bfcl_runner_shape": runner,
        "shape_deltas": suspected,
        "suspected_gap": suspected[0] if suspected else "not_reproduced_by_shape_delta_gate",
        "minimal_fix_recommended": "no_runtime_fix_yet_prepare_exact_bfcl_request_capture_or_patch_tool_choice_token_policy_after_review" if suspected else "no_fix_recommended",
        "not_measurement_evidence": True,
    }
    return report


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BFCL Runner Request Shape Delta",
        "",
        "Status: no-provider shape-only artifact. No provider request, live telemetry rerun, BFCL smoke, scorer, full/default baseline, candidate activation, performance, +3pp, or Huawei path was run.",
        "",
        f"- suspected_gap: `{report['suspected_gap']}`",
        f"- shape_deltas: `{', '.join(report['shape_deltas'])}`",
        f"- minimal_fix_recommended: `{report['minimal_fix_recommended']}`",
        "",
        "The artifact records labels and buckets only. It intentionally omits raw BFCL case content, prompts, gold/reference/expected material, scorer diffs, provider payloads, logs, traces, endpoint/key values, and candidate outputs.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(args.md_output, report)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
