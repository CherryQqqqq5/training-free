#!/usr/bin/env python3
"""Check the sanitized provider payload shape diff artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.build_rashe_provider_payload_shape_diff import DEFAULT_JSON, build_report

REQUIRED_FALSE = (
    "raw_payload_persisted",
    "raw_prompt_persisted",
    "source_input_read",
    "diagnostic_written",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
)
FORBIDDEN_VALUE_FRAGMENTS = (
    "case_id",
    "raw_trace_path",
    "raw provider",
    "provider payload",
    "gold value",
    "expected value",
    "reference value",
    "scorer diff",
    "candidate output",
    "feedback value",
    "gpt-4o fallback: true",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _walk_string_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[str] = []
        for child in value.values():
            values.extend(_walk_string_values(child))
        return values
    if isinstance(value, list):
        values = []
        for child in value:
            values.extend(_walk_string_values(child))
        return values
    if isinstance(value, str):
        return [value]
    return []


def validate(report: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    expected = build_report()
    for key in [
        "report_scope",
        "successful_synthetic_variant",
        "phase_b_payload_builder",
        "synthetic_payload_shape",
        "phase_b_planned_payload_shape",
    ]:
        if report.get(key) != expected.get(key):
            blockers.append(f"shape_diff_{key}_drift")
    if report.get("alignment_passed") is not True:
        blockers.append(f"shape_diff_alignment_not_passed:{report.get('blockers')!r}")
    if report.get("blockers") not in ([], None):
        blockers.append("shape_diff_blockers_not_empty")
    for key in REQUIRED_FALSE:
        if report.get(key) is not False:
            blockers.append(f"shape_diff_{key}_not_false:{report.get(key)!r}")
    if report.get("shape_fields_only") is not True:
        blockers.append("shape_diff_shape_fields_only_not_true")
    phase_shape = report.get("phase_b_planned_payload_shape") if isinstance(report.get("phase_b_planned_payload_shape"), dict) else {}
    synthetic_shape = report.get("synthetic_payload_shape") if isinstance(report.get("synthetic_payload_shape"), dict) else {}
    for key in ["model", "message_count", "messages_role_sequence", "tools_count", "tool_choice_form", "token_field_name", "temperature_present"]:
        if phase_shape.get(key) != synthetic_shape.get(key):
            blockers.append(f"shape_diff_phase_b_not_aligned:{key}")
    flags = phase_shape.get("tool_schema_feature_flags") if isinstance(phase_shape.get("tool_schema_feature_flags"), dict) else {}
    for flag in ["function_tool", "parameters_type_object", "required_present", "additional_properties_false"]:
        if flags.get(flag) is not True:
            blockers.append(f"shape_diff_phase_b_missing_tool_flag:{flag}")
    if flags.get("strict_present") is not False:
        blockers.append("shape_diff_phase_b_strict_present")
    encoded_values = "\n".join(_walk_string_values(report)).lower()
    for fragment in FORBIDDEN_VALUE_FRAGMENTS:
        if fragment in encoded_values:
            blockers.append(f"shape_diff_forbidden_value_fragment:{fragment}")
    return blockers


def check(path: Path = DEFAULT_JSON) -> dict[str, Any]:
    report = load_json(path)
    blockers = validate(report)
    return {
        "report_scope": "rashe_provider_payload_shape_diff_check",
        "artifact_path": str(path),
        "successful_synthetic_variant": report.get("successful_synthetic_variant"),
        "phase_b_payload_builder": report.get("phase_b_payload_builder"),
        "alignment_passed": report.get("alignment_passed"),
        "shape_fields_only": report.get("shape_fields_only"),
        "provider_payload_shape_diff_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "rashe_provider_payload_shape_diff_check",
            "artifact_path": str(args.artifact),
            "provider_payload_shape_diff_passed": False,
            "blockers": [f"shape_diff_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["provider_payload_shape_diff_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
