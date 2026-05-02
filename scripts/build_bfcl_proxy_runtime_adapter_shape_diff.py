#!/usr/bin/env python3
"""Build a sanitized BFCL proxy/runtime adapter envelope shape diff."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.run_bfcl_measurement_provider_protocol_debug import build_synthetic_payload
from scripts.check_bfcl_proxy_runtime_adapter_debug_packet import SIGNED_RUN_IDS_BY_CATEGORY

DEFAULT_JSON = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_runtime_adapter_envelope_shape_diff.json")
DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_runtime_adapter_envelope_shape_diff.md")
PROTOCOL_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_measurement_provider_protocol_debug_compact.json")
SMOKE_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_stage1_smoke_run_id_manifest.json")


def _bucket(text: Any) -> str:
    length = len(str(text or ""))
    if length == 0:
        return "empty"
    if length <= 64:
        return "short"
    if length <= 512:
        return "medium"
    return "long"


def _hash_flags(flags: dict[str, Any]) -> str:
    encoded = json.dumps(flags, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _tool_choice_mode(value: Any) -> str:
    if value == "required":
        return "required_string"
    if value == "auto":
        return "auto_string"
    if isinstance(value, dict) and value.get("type") == "function":
        return "function_object"
    if value is None:
        return "absent"
    return "other"


def _token_presence(payload: dict[str, Any]) -> dict[str, bool]:
    return {
        "max_tokens": "max_tokens" in payload,
        "max_completion_tokens": "max_completion_tokens" in payload,
    }


def _shape_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    tools = payload.get("tools") if isinstance(payload.get("tools"), list) else []
    first_tool = tools[0] if tools and isinstance(tools[0], dict) else {}
    function = first_tool.get("function") if isinstance(first_tool.get("function"), dict) else {}
    parameters = function.get("parameters") if isinstance(function.get("parameters"), dict) else {}
    properties = parameters.get("properties") if isinstance(parameters.get("properties"), dict) else {}
    flags = {
        "function_tool": first_tool.get("type") == "function",
        "function_name_present": isinstance(function.get("name"), str) and bool(function.get("name")),
        "parameters_type_object": parameters.get("type") == "object",
        "properties_present": bool(properties),
        "required_present": isinstance(parameters.get("required"), list) and bool(parameters.get("required")),
        "additional_properties_false": parameters.get("additionalProperties") is False,
        "strict_present": "strict" in function,
        "enum_present": any(isinstance(value, dict) and "enum" in value for value in properties.values()),
    }
    return {
        "route_model": payload.get("model"),
        "request_top_level_keys": sorted(str(key) for key in payload),
        "message_count": len(messages),
        "role_sequence": [message.get("role") for message in messages if isinstance(message, dict)],
        "content_length_buckets": [_bucket(message.get("content")) for message in messages if isinstance(message, dict)],
        "tools_count": len(tools),
        "tool_schema_structural_flags": flags,
        "tool_schema_structural_hash": _hash_flags(flags),
        "tool_choice_mode": _tool_choice_mode(payload.get("tool_choice")),
        "token_field_presence": _token_presence(payload),
        "temperature_presence": "temperature" in payload,
        "timeout_streaming_flags": {"timeout_seconds_present": True, "streaming_enabled": False},
        "parser_expected_response_keys": ["choices", "message", "tool_calls", "function.name"],
        "empty_response_handling_path_labels": ["empty_model_response_stop_gate", "missing_tool_call_stop_gate", "openai_response_shape_stop_gate"],
    }


def _proxy_runtime_planned_shape() -> dict[str, Any]:
    flags = {
        "function_tool": True,
        "function_name_present": True,
        "parameters_type_object": True,
        "properties_present": True,
        "required_present": True,
        "additional_properties_false": "not_enforced_by_current_bfcl_adapter_shape",
        "strict_present": False,
        "enum_present": "unknown_until_adapter_capture",
    }
    return {
        "route_model": "gpt-4.1",
        "request_top_level_keys": ["messages_or_input", "model", "tool_choice", "tools"],
        "message_count": "bfcl_runtime_variable",
        "role_sequence": ["bfcl_runtime_variable"],
        "content_length_buckets": ["bucketed_only_runtime_variable"],
        "tools_count": "bfcl_runtime_variable_positive",
        "tool_schema_structural_flags": flags,
        "tool_schema_structural_hash": _hash_flags(flags),
        "tool_choice_mode": "required_string",
        "token_field_presence": {"max_tokens": "unknown_until_adapter_capture", "max_completion_tokens": "unknown_until_adapter_capture"},
        "temperature_presence": "unknown_until_adapter_capture",
        "timeout_streaming_flags": {"timeout_seconds_present": "proxy_runtime_configured", "streaming_enabled": False},
        "parser_expected_response_keys": ["choices", "message", "tool_calls", "function.name"],
        "empty_response_handling_path_labels": ["decode_execute_empty_string_returns_empty_call_list", "bfcl_runner_stops_on_empty_model_response"],
    }


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _reviewed_run_refs(manifest: dict[str, Any]) -> dict[str, list[str]]:
    by_category = manifest.get("run_ids_by_category") if isinstance(manifest.get("run_ids_by_category"), dict) else {}
    return {str(category): [str(value) for value in values] for category, values in by_category.items() if isinstance(values, list)}


def build_report() -> dict[str, Any]:
    protocol = _load_json(PROTOCOL_ARTIFACT)
    manifest = _load_json(SMOKE_MANIFEST)
    synthetic_shape = _shape_from_payload(build_synthetic_payload())
    proxy_shape = _proxy_runtime_planned_shape()
    run_refs = _reviewed_run_refs(manifest)
    blockers: list[str] = []
    if run_refs != SIGNED_RUN_IDS_BY_CATEGORY:
        blockers.append("reviewed_run_id_references_drift")
    records = protocol.get("records") if isinstance(protocol.get("records"), list) else []
    record = records[0] if records and isinstance(records[0], dict) else {}
    contract = record.get("response_contract") if isinstance(record.get("response_contract"), dict) else {}
    if protocol.get("provider_request_executed") is not True or contract.get("tool_call_present") is not True:
        blockers.append("successful_synthetic_protocol_artifact_not_confirmed")
    risk_labels = []
    if synthetic_shape["tool_choice_mode"] != proxy_shape["tool_choice_mode"]:
        risk_labels.append("tool_choice_form_differs_function_object_vs_required_string")
    if proxy_shape["tool_schema_structural_flags"].get("additional_properties_false") is not True:
        risk_labels.append("proxy_adapter_additional_properties_flag_unknown_or_not_enforced")
    if proxy_shape["token_field_presence"]["max_tokens"] == "unknown_until_adapter_capture":
        risk_labels.append("proxy_adapter_token_field_unknown_until_capture")
    return {
        "artifact_kind": "bfcl_proxy_runtime_adapter_envelope_shape_diff",
        "approval_status": "prepared",
        "provider_request_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_full_eval_executed": False,
        "scorer_executed": False,
        "source_input_read": False,
        "diagnostic_written": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "scorer_feedback_tuning_enabled": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "raw_request_persisted": False,
        "raw_response_persisted": False,
        "raw_header_persisted": False,
        "raw_body_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "raw_prompt_persisted": False,
        "raw_case_content_persisted": False,
        "endpoint_value_committed": False,
        "api_key_value_committed": False,
        "provider_profile": "Chuangzhi/Novacode",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "stopped_smoke_facts": {
            "exact_8_ids_materialized": True,
            "run_id_count": 8,
            "stopped_on": "repeated_empty_model_response",
            "progress_observed": "6/8",
            "committed_smoke_artifacts": False,
            "committed_results": False,
            "performance_claim": False,
        },
        "reviewed_run_id_references": run_refs,
        "successful_synthetic_provider_contract_shape": synthetic_shape,
        "bfcl_proxy_runtime_planned_shape": proxy_shape,
        "parser_alignment": {
            "synthetic_expected_response_keys": synthetic_shape["parser_expected_response_keys"],
            "bfcl_decode_execute_response_keys": proxy_shape["parser_expected_response_keys"],
            "empty_response_handling_path_labels": proxy_shape["empty_response_handling_path_labels"],
        },
        "shape_diff_high_level_conclusion": "synthetic_provider_contract_passed_but_bfcl_proxy_runtime_adapter_envelope_requires_review_before_retry",
        "adapter_risk_labels": risk_labels,
        "shape_fields_only": True,
        "blockers": blockers,
        "bfcl_proxy_runtime_adapter_shape_diff_passed": not blockers,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# BFCL Proxy Runtime Adapter Envelope Shape Diff",
        "",
        "Status: sanitized shape-only preparation artifact. No provider call, BFCL smoke retry, scorer, candidate activation, performance, +3pp, or Huawei path is authorized.",
        "",
        f"- route: `{report['active_profile']}/{report['route_model']}`",
        "- stopped_smoke: `repeated_empty_model_response`, progress `6/8`, committed artifacts `false`",
        f"- shape_fields_only: `{str(report['shape_fields_only']).lower()}`",
        f"- conclusion: `{report['shape_diff_high_level_conclusion']}`",
        f"- adapter_risk_labels: `{report['adapter_risk_labels']}`",
        "",
        "The successful synthetic provider contract proves the env-only novacode gpt-4.1 tool-call path can return an OpenAI-compatible tool call. The stopped BFCL smoke used the reviewed eight run IDs but failed on repeated empty responses before any smoke artifact was committed. This artifact records only envelope and parser structure; it does not include raw prompts, provider payloads, response bodies, headers, logs, traces, case content, gold/reference/expected values, scorer diffs, endpoint/key values, source nonce mappings, or candidate output.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = build_report()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(args.md_output, report)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    if args.strict and not report["bfcl_proxy_runtime_adapter_shape_diff_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
