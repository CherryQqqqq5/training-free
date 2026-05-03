#!/usr/bin/env python3
"""Check the protocol-status-after-nonempty-decode patch gate packet."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_protocol_status_after_nonempty_decode_patch_gate_packet.json")
PATCH_NAME = "bfcl_protocol_status_after_nonempty_decode_materialization_shape_guard"
PATCH_KIND = "result_materialization_protocol_status_guard"
TARGET_SCOPE = "bfcl_measurement_generate_result_materialization_only"
CONDITION = "clean_nonempty_decoded_execution_output_would_materialize_as_protocol_error_shape"
BEHAVIOR = "avoid_protocol_error_shape_for_clean_nonempty_decode_preserve_explicit_errors"
SOURCE_STAGE = "materialization_entry_shape_protocol_error_after_nonempty_decode"
REQUIRED_FALSE_KEYS = (
    "authorized",
    "behavior_patch_authorized",
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
    "fallback_allowed",
    "gpt_4o_fallback_enabled",
    "gpt_5_2_active",
    "openrouter_enabled",
)
REQUIRED_SCOPE = {
    "avoid_materializing_clean_nonempty_decode_as_protocol_error_shape",
    "preserve_explicit_handler_error_phrases_as_protocol_error",
    "preserve_structured_error_exception_keys_as_protocol_error",
    "true_empty_remains_empty",
    "prior_generated_marker_behavior_unchanged",
    "no_provider_route_model_changes",
    "no_parser_decode_changes",
    "no_scorer_eval_baseline_path",
    "no_candidate_runtime_skill_logic",
    "no_performance_path",
    "no_claim_or_fix_for_irrelevance_unknowns_or_broader_8id_readiness",
}
FORBIDDEN_SCOPE = {
    "provider",
    "route",
    "model",
    "parser_decode",
    "scorer",
    "eval_baseline",
    "candidate",
    "runtime_skill_logic",
    "performance",
    "irrelevance_unknown_fix_claim",
    "broader_8id_readiness_claim",
    "classifier_broadening",
}
REQUIRED_CRITERIA = {
    "clean_nonempty_decoded_execution_output_does_not_materialize_protocol_error_shape",
    "clean_nonempty_decoded_execution_output_materializes_compact_detectable_nonempty_generated_equivalent_shape",
    "explicit_handler_error_phrase_remains_protocol_error",
    "structured_error_exception_key_remains_protocol_error",
    "true_empty_remains_empty",
    "prior_generated_marker_behavior_unchanged",
    "provider_route_parser_decode_scorer_candidate_baseline_performance_unchanged",
    "irrelevance_unknowns_and_broader_8id_readiness_not_claimed_fixed",
    "artifact_boundary_sanitized_no_endpoint_key_material",
}
ALLOWED_RAWISH_KEYS = {
    "no_provider_required",
    "provider_request_authorized",
    "source_replay_artifact",
}
FORBIDDEN_KEY_RE = re.compile(
    r"(raw_(?:prompt|case|provider|payload|log|trace|response|text|tool)|prompt_text|case_content|provider_payload|provider_body|headers|endpoint_value|api_key_value|gold|reference|expected|scorer_diff|candidate_output|secret)",
    re.IGNORECASE,
)
FORBIDDEN_VALUE_RE = re.compile(
    ("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|endpoint " + "value|api " + "key|raw " + "prompt|raw " + "case|provider " + "payload|scorer " + "diff|candidate " + "output"),
    re.IGNORECASE,
)
BROAD_SCOPE_TERMS = ("provider", "route", "model", "parser", "decode", "scorer", "candidate", "runtime_skill", "baseline", "performance", "irrelevance", "8id", "classifier")
ALLOWED_BROAD_SCOPE_PHRASES = REQUIRED_SCOPE | FORBIDDEN_SCOPE | REQUIRED_CRITERIA


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
        if key and key not in ALLOWED_RAWISH_KEYS and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def _unexpected_broad_scope(scope: list[Any]) -> list[str]:
    blockers: list[str] = []
    for item in scope:
        text = str(item)
        if text in ALLOWED_BROAD_SCOPE_PHRASES:
            continue
        lowered = text.lower()
        if any(term in lowered for term in BROAD_SCOPE_TERMS):
            blockers.append(f"patch_scope_broadened:{text}")
    return blockers


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_protocol_status_after_nonempty_decode_patch_gate_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "pending":
        blockers.append(f"approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("route_drift")
    for key in REQUIRED_FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"{key}_not_false:{data.get(key)!r}")
    expected = {
        "requested_patch_name": PATCH_NAME,
        "requested_patch_kind": PATCH_KIND,
        "requested_target_scope": TARGET_SCOPE,
        "requested_condition": CONDITION,
        "requested_behavior": BEHAVIOR,
    }
    for key, value in expected.items():
        if data.get(key) != value:
            blockers.append(f"{key}_invalid:{data.get(key)!r}")
    scope = data.get("requested_future_patch_scope")
    if not isinstance(scope, list):
        blockers.append("requested_future_patch_scope_not_list")
        scope = []
    scope_set = {str(item) for item in scope}
    if not REQUIRED_SCOPE.issubset(scope_set):
        blockers.append(f"required_patch_scope_missing:{sorted(REQUIRED_SCOPE - scope_set)!r}")
    blockers.extend(_unexpected_broad_scope(scope))
    forbidden = data.get("forbidden_patch_scope")
    if not isinstance(forbidden, list):
        blockers.append("forbidden_patch_scope_not_list")
        forbidden = []
    forbidden_set = {str(item) for item in forbidden}
    if not FORBIDDEN_SCOPE.issubset(forbidden_set):
        blockers.append(f"forbidden_patch_scope_missing:{sorted(FORBIDDEN_SCOPE - forbidden_set)!r}")
    criteria = data.get("offline_acceptance_criteria")
    if not isinstance(criteria, list):
        blockers.append("offline_acceptance_criteria_not_list")
        criteria = []
    criteria_set = {str(item) for item in criteria}
    if not REQUIRED_CRITERIA.issubset(criteria_set):
        blockers.append(f"offline_acceptance_criteria_missing:{sorted(REQUIRED_CRITERIA - criteria_set)!r}")
    for key in ("no_provider_required", "no_live_telemetry_required", "no_bfcl_generate_required", "no_performance_claim"):
        if data.get(key) is not True:
            blockers.append(f"{key}_not_true:{data.get(key)!r}")
    if data.get("source_replay_stage") != SOURCE_STAGE:
        blockers.append(f"source_replay_stage_invalid:{data.get('source_replay_stage')!r}")
    if not str(data.get("source_replay_artifact", "")).endswith("bfcl_protocol_status_after_nonempty_decode_replay.json"):
        blockers.append(f"source_replay_artifact_invalid:{data.get('source_replay_artifact')!r}")
    blockers.extend(_scan(data))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> dict[str, Any]:
    packet = _load(path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "bfcl_protocol_status_after_nonempty_decode_patch_gate_check",
        "packet_path": str(path),
        "bfcl_protocol_status_after_nonempty_decode_patch_gate_passed": not blockers,
        "approval_status": packet.get("approval_status"),
        "behavior_patch_authorized": packet.get("behavior_patch_authorized"),
        "requested_patch_kind": packet.get("requested_patch_kind"),
        "requested_target_scope": packet.get("requested_target_scope"),
        "source_replay_stage": packet.get("source_replay_stage"),
        "offline_acceptance_criteria_count": len(packet.get("offline_acceptance_criteria", [])) if isinstance(packet.get("offline_acceptance_criteria"), list) else 0,
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
        summary = {"report_scope": "bfcl_protocol_status_after_nonempty_decode_patch_gate_check", "bfcl_protocol_status_after_nonempty_decode_patch_gate_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_protocol_status_after_nonempty_decode_patch_gate_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
