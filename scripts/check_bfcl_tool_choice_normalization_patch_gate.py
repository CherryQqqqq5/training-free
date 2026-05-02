#!/usr/bin/env python3
"""Check the BFCL tool-choice normalization patch gate and result."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_tool_choice_normalization_patch_gate_packet.json")
DEFAULT_DESIGN = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_tool_choice_normalization_patch_design.json")
DEFAULT_RESULT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_tool_choice_normalization_patch_result.json")
PATCH_NAME = "bfcl_measurement_responses_to_chat_tool_choice_normalization"
PATCH_KIND = "proxy_normalization"
TARGET_SCOPE = "bfcl_measurement_generate_path_only"
CONDITION = "tools_present_and_tool_choice_missing_or_none"
NORMALIZED_TOOL_CHOICE = "required"
REQUIRED_FALSE_PACKET = (
    "authorized",
    "patch_authorized",
    "provider_request_authorized",
    "live_telemetry_authorized",
    "bfcl_generate_authorized",
    "bfcl_smoke_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "gpt_4o_fallback_enabled",
    "gpt_5_2_active",
    "openrouter_enabled",
)
REQUIRED_FALSE_DESIGN = (
    "patch_authorized",
    "provider_request_authorized",
    "live_telemetry_authorized",
    "bfcl_generate_authorized",
    "bfcl_smoke_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
    "candidate_runtime_activation_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "gpt_4o_fallback_enabled",
    "gpt_5_2_active",
    "openrouter_enabled",
)
REQUIRED_FALSE_RESULT = (
    "provider_request_authorized",
    "live_telemetry_authorized",
    "bfcl_generate_authorized",
    "bfcl_smoke_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "full_baseline_authorized",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "gpt_4o_fallback_enabled",
    "gpt_5_2_active",
    "openrouter_enabled",
)
REQUIRED_FORBIDDEN_SCOPE = {"candidate", "scorer", "baseline", "performance", "general_runtime_if_not_config_gated"}
FORBIDDEN_KEY_RE = re.compile(
    r"(raw_(?:prompt|case|provider|payload|log|trace|response|text|tool)|prompt_text|case_content|provider_payload|provider_body|headers|endpoint_value|api_key_value|gold|reference|expected|scorer_diff|candidate_output)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz" + "|boyue" + "richdata|raw prompt|raw case|provider payload|scorer diff|gold/reference/expected|candidate output"),
    re.IGNORECASE,
)
ALLOWED_COMPACT_FIELD_NAMES = {"no_provider_required", "no_bfcl_generate_required"}


def _load(path: Path) -> dict[str, Any]:
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


def _scan(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    sep = "."
    for path, value in _walk(data):
        key = path[-1] if path else ""
        if key and key not in ALLOWED_COMPACT_FIELD_NAMES and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{sep.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"forbidden_value:{sep.join(path)}")
    return sorted(set(blockers))


def _check_route(data: dict[str, Any], label: str) -> list[str]:
    blockers: list[str] = []
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append(f"{label}_route_drift")
    for key in ("gpt_4o_fallback_enabled", "gpt_5_2_active", "openrouter_enabled"):
        if data.get(key) is not False:
            blockers.append(f"{label}_{key}_not_false:{data.get(key)!r}")
    return blockers


def _check_patch_fields(data: dict[str, Any], label: str, prefix: str = "") -> list[str]:
    blockers: list[str] = []
    expected = {
        f"{prefix}patch_name": PATCH_NAME,
        f"{prefix}patch_kind": PATCH_KIND,
        f"{prefix}target_scope": TARGET_SCOPE,
        f"{prefix}condition": CONDITION,
        f"{prefix}normalized_tool_choice": NORMALIZED_TOOL_CHOICE,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"{label}_{key}_invalid:{data.get(key)!r}")
    return blockers


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_tool_choice_normalization_patch_gate_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"packet_approval_status_invalid:{data.get('approval_status')!r}")
    for key in REQUIRED_FALSE_PACKET:
        if data.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{data.get(key)!r}")
    expected = {
        "requested_patch_name": PATCH_NAME,
        "requested_patch_kind": PATCH_KIND,
        "requested_target_scope": TARGET_SCOPE,
        "requested_condition": CONDITION,
        "requested_normalized_tool_choice": NORMALIZED_TOOL_CHOICE,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"packet_{key}_invalid:{data.get(key)!r}")
    blockers.extend(_check_route(data, "packet"))
    blockers.extend(f"packet_{item}" for item in _scan(data))
    return sorted(set(blockers))


def validate_design(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_tool_choice_normalization_patch_design":
        blockers.append(f"design_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"design_approval_status_invalid:{data.get('approval_status')!r}")
    blockers.extend(_check_patch_fields(data, "design"))
    for key in REQUIRED_FALSE_DESIGN:
        if data.get(key) is not False:
            blockers.append(f"design_{key}_not_false:{data.get(key)!r}")
    if data.get("no_provider_required") is not True:
        blockers.append(f"design_no_provider_required_not_true:{data.get('no_provider_required')!r}")
    if data.get("no_bfcl_generate_required") is not True:
        blockers.append(f"design_no_bfcl_generate_required_not_true:{data.get('no_bfcl_generate_required')!r}")
    if data.get("no_performance_claim") is not True:
        blockers.append(f"design_no_performance_claim_not_true:{data.get('no_performance_claim')!r}")
    forbidden_scope = set(data.get("forbidden_scope") or [])
    if not REQUIRED_FORBIDDEN_SCOPE.issubset(forbidden_scope):
        blockers.append(f"design_forbidden_scope_incomplete:{sorted(forbidden_scope)!r}")
    rollback = data.get("rollback_plan")
    if not isinstance(rollback, list) or len(rollback) < 2:
        blockers.append("design_rollback_plan_missing")
    offline_tests = data.get("offline_tests_required")
    if not isinstance(offline_tests, list) or len(offline_tests) < 5:
        blockers.append("design_offline_tests_required_incomplete")
    else:
        required_test_terms = ("missing_tool_choice", "tools_absent", "route_remains", "candidate_scorer_baseline_performance")
        joined = "\n".join(str(item) for item in offline_tests)
        for term in required_test_terms:
            if term not in joined:
                blockers.append(f"design_offline_tests_missing:{term}")
    blockers.extend(_check_route(data, "design"))
    blockers.extend(f"design_{item}" for item in _scan(data))
    return sorted(set(blockers))


def validate_result(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_tool_choice_normalization_patch_result":
        blockers.append(f"result_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "completed":
        blockers.append(f"result_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("patch_authorized") is not True:
        blockers.append(f"result_patch_authorized_not_true:{data.get('patch_authorized')!r}")
    if data.get("patch_completed") is not True:
        blockers.append(f"result_patch_completed_not_true:{data.get('patch_completed')!r}")
    blockers.extend(_check_patch_fields(data, "result"))
    if data.get("condition") != CONDITION:
        blockers.append(f"result_condition_invalid:{data.get('condition')!r}")
    for key in REQUIRED_FALSE_RESULT:
        if data.get(key) is not False:
            blockers.append(f"result_{key}_not_false:{data.get(key)!r}")
    touched = set(data.get("code_paths_touched") or [])
    required_paths = {"src/grc/runtime/proxy.py", "configs/runtime_bfcl_structured.yaml"}
    if not required_paths.issubset(touched):
        blockers.append(f"result_code_paths_touched_incomplete:{sorted(touched)!r}")
    blockers.extend(_check_route(data, "result"))
    blockers.extend(f"result_{item}" for item in _scan(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, design_path: Path = DEFAULT_DESIGN, result_path: Path = DEFAULT_RESULT) -> dict[str, Any]:
    packet = _load(packet_path)
    design = _load(design_path)
    blockers = validate_packet(packet) + validate_design(design)
    result_present = result_path.exists()
    result: dict[str, Any] = {}
    if result_present:
        result = _load(result_path)
        blockers.extend(validate_result(result))
    return {
        "report_scope": "bfcl_tool_choice_normalization_patch_gate_check",
        "packet_path": str(packet_path),
        "design_path": str(design_path),
        "result_path": str(result_path) if result_present else None,
        "bfcl_tool_choice_normalization_patch_gate_passed": not blockers,
        "patch_name": design.get("patch_name"),
        "patch_kind": design.get("patch_kind"),
        "target_scope": design.get("target_scope"),
        "condition": design.get("condition"),
        "normalized_tool_choice": design.get("normalized_tool_choice"),
        "patch_authorized": result.get("patch_authorized", packet.get("patch_authorized")),
        "patch_completed": result.get("patch_completed", False),
        "blockers": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.design, args.result)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "bfcl_tool_choice_normalization_patch_gate_check",
            "bfcl_tool_choice_normalization_patch_gate_passed": False,
            "blockers": [f"load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_tool_choice_normalization_patch_gate_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
