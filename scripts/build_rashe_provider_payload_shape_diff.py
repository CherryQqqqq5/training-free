#!/usr/bin/env python3
"""Build sanitized payload shape diff for protocol-debug/source-diagnostic alignment."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_rashe_provider_protocol_debug_preflight import payload_for_variant
from scripts import rashe_source_provider_client as source_client

DEFAULT_JSON = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_payload_shape_diff.json")
DEFAULT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_payload_shape_diff.md")
SIGNED_SYNTHETIC_VARIANT = "baseline_chat_tools_required"
FORBIDDEN_FRAGMENTS = (
    "case_id",
    "raw_trace_path",
    "provider_payload_value",
    "gold_value",
    "expected_value",
    "reference_value",
    "scorer_diff_value",
    "candidate_output",
    "feedback_value",
    "gpt-4o",
)


def _bucket(text: str) -> str:
    length = len(text)
    if length == 0:
        return "empty"
    if length <= 32:
        return "short"
    if length <= 160:
        return "medium"
    return "long"


def _tool_choice_form(value: Any) -> str:
    if value == "auto":
        return "auto"
    if isinstance(value, dict) and value.get("type") == "function":
        return "function_object"
    if value is None:
        return "absent"
    return "other"


def _token_field(payload: dict[str, Any]) -> str | None:
    fields = [field for field in ("max_tokens", "max_completion_tokens") if field in payload]
    return fields[0] if len(fields) == 1 else None


def payload_shape(payload: dict[str, Any]) -> dict[str, Any]:
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    tools = payload.get("tools") if isinstance(payload.get("tools"), list) else []
    first_tool = tools[0] if tools and isinstance(tools[0], dict) else {}
    function = first_tool.get("function") if isinstance(first_tool.get("function"), dict) else {}
    parameters = function.get("parameters") if isinstance(function.get("parameters"), dict) else {}
    properties = parameters.get("properties") if isinstance(parameters.get("properties"), dict) else {}
    return {
        "model": payload.get("model"),
        "message_count": len(messages),
        "messages_role_sequence": [message.get("role") for message in messages if isinstance(message, dict)],
        "content_length_buckets": [_bucket(str(message.get("content") or "")) for message in messages if isinstance(message, dict)],
        "tools_count": len(tools),
        "tool_schema_feature_flags": {
            "function_tool": first_tool.get("type") == "function",
            "parameters_type_object": parameters.get("type") == "object",
            "required_present": isinstance(parameters.get("required"), list) and bool(parameters.get("required")),
            "additional_properties_false": parameters.get("additionalProperties") is False,
            "strict_present": "strict" in function,
            "enum_present": any(isinstance(value, dict) and "enum" in value for value in properties.values()),
        },
        "tool_choice_form": _tool_choice_form(payload.get("tool_choice")),
        "token_field_name": _token_field(payload),
        "temperature_present": "temperature" in payload,
    }


def planned_source_payload() -> dict[str, Any]:
    return source_client.build_source_diagnostic_chat_payload(
        {
            "category": "agentic_web_search",
            "ordinal": 0,
            "provider_profile": source_client.SIGNED_PROVIDER_PROFILE,
            "model": source_client.SIGNED_MODEL,
            "compact_sanitized_only": True,
            "raw_payload_capture_authorized": False,
            "raw_trace_capture_authorized": False,
            "candidate_generation_authorized": False,
            "scorer_authorized": False,
            "performance_evidence": False,
        }
    )


def build_report() -> dict[str, Any]:
    synthetic_shape = payload_shape(payload_for_variant(SIGNED_SYNTHETIC_VARIANT))
    phase_b_shape = payload_shape(planned_source_payload())
    compared = [
        "model",
        "message_count",
        "messages_role_sequence",
        "tools_count",
        "tool_choice_form",
        "token_field_name",
        "temperature_present",
    ]
    mismatches = [field for field in compared if synthetic_shape.get(field) != phase_b_shape.get(field)]
    synthetic_flags = synthetic_shape["tool_schema_feature_flags"]
    phase_b_flags = phase_b_shape["tool_schema_feature_flags"]
    required_flags = ["function_tool", "parameters_type_object", "required_present", "additional_properties_false"]
    for flag in required_flags:
        if synthetic_flags.get(flag) is not True or phase_b_flags.get(flag) is not True:
            mismatches.append(f"tool_schema_feature_flags.{flag}")
    blockers = []
    if mismatches:
        blockers.append("payload_shape_mismatch:" + ",".join(mismatches))
    if phase_b_flags.get("strict_present") is True:
        blockers.append("phase_b_tool_schema_strict_present")
    return {
        "report_scope": "rashe_provider_payload_shape_diff",
        "successful_synthetic_variant": SIGNED_SYNTHETIC_VARIANT,
        "phase_b_payload_builder": "scripts.rashe_source_provider_client:build_source_diagnostic_chat_payload",
        "raw_payload_persisted": False,
        "raw_prompt_persisted": False,
        "source_input_read": False,
        "diagnostic_written": False,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "shape_fields_only": True,
        "synthetic_payload_shape": synthetic_shape,
        "phase_b_planned_payload_shape": phase_b_shape,
        "alignment_passed": not blockers,
        "blockers": blockers,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# RASHE Provider Payload Shape Diff",
        "",
        "Status: sanitized shape-only protocol alignment artifact. No provider call, Phase B execution, diagnostics write, source input read, candidate, scorer, performance, +3pp, or Huawei path is authorized by this artifact.",
        "",
        f"- successful_synthetic_variant: `{report['successful_synthetic_variant']}`",
        f"- phase_b_payload_builder: `{report['phase_b_payload_builder']}`",
        f"- alignment_passed: `{str(report['alignment_passed']).lower()}`",
        f"- blockers: `{report['blockers']}`",
        "",
        "## High-Level Shape Conclusion",
        "",
        "The Phase B planned provider payload now uses the same OpenAI-compatible chat tools envelope as the successful synthetic protocol variant: fixed `gpt-4.1`, one user message, one function tool, function-object `tool_choice`, `max_tokens`, and no raw persistence.",
        "",
        "Only field-level structure is recorded. Raw prompt text, raw tool schema text, arguments, case IDs, gold/expected/reference, provider payloads, diagnostics, candidates, scorer data, and performance claims are forbidden.",
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
    encoded = json.dumps(report, indent=2, sort_keys=True)
    lowered = encoded.lower()
    for fragment in FORBIDDEN_FRAGMENTS:
        if fragment in lowered:
            report["blockers"].append(f"shape_report_forbidden_fragment:{fragment}")
    report["alignment_passed"] = not report["blockers"]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(args.md_output, report)
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    if args.strict and not report["alignment_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
