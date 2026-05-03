#!/usr/bin/env python3
"""Check Stage 1G materialization/classifier-after-decode debug packet and artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_PACKET = ARTIFACT_ROOT / "bfcl_materialization_classifier_after_decode_debug_packet.json"
DEFAULT_ARTIFACT = ARTIFACT_ROOT / "bfcl_materialization_classifier_after_decode_debug.json"
FALSE_PACKET_KEYS = (
    "authorized", "provider_request_authorized", "live_telemetry_authorized", "bfcl_generate_authorized",
    "bfcl_smoke_authorized", "bfcl_evaluate_authorized", "scorer_authorized", "full_baseline_authorized",
    "candidate_runtime_activation_authorized", "candidate_jsonl_authorized", "candidate_pool_ready",
    "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "fallback_allowed",
    "gpt_4o_fallback_allowed", "gpt_5_2_active", "openrouter_allowed",
)
FALSE_ARTIFACT_KEYS = (
    "provider_request_executed", "live_telemetry_executed", "bfcl_generate_executed", "bfcl_smoke_executed",
    "bfcl_evaluate_executed", "scorer_executed", "full_baseline_executed", "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized", "candidate_pool_ready", "performance_evidence", "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
)
VARIANTS = [
    "valid_nonempty_decoded_tool_call_shape",
    "nonempty_decoded_alternate_layout",
    "true_empty_decoded_output",
    "malformed_decoded_output_shape",
    "post_decode_exception_after_nonempty_decode",
    "missing_materialized_file_path",
    "nonempty_materialized_result_with_classifier_path",
]
ALLOWED_RAWISH_KEYS = {
    "no_provider",
    "provider_request_authorized",
    "provider_request_executed",
    "result_layout_expected_label",
    "target_live_capture_artifact",
}
FORBIDDEN_KEY_RE = re.compile(r"(raw|prompt|case_content|provider_payload|provider_request|provider_response|logs?|traces?|tool_args?|tool_name|function_name|endpoint|api_key|gold|reference|expected|scorer_diff|candidate_output)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|" + "api" + "cz" + "|" + "boyue" + "richdata|provider payload|raw prompt|raw case|scorer diff|candidate output|endpoint value|api key"), re.IGNORECASE)


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
    blockers = []
    for path, value in _walk(data):
        key = path[-1] if path else ""
        if key and key not in ALLOWED_RAWISH_KEYS and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers = []
    if data.get("artifact_kind") != "bfcl_materialization_classifier_after_decode_debug_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"packet_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("packet_route_drift")
    if data.get("no_provider_required") is not True or data.get("synthetic_fixtures_only") is not True:
        blockers.append("packet_no_provider_or_synthetic_not_true")
    for key in FALSE_PACKET_KEYS:
        if data.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{data.get(key)!r}")
    blockers.extend(f"packet_{item}" for item in _scan(data))
    return sorted(set(blockers))


def validate_artifact(data: dict[str, Any]) -> list[str]:
    blockers = []
    if data.get("artifact_kind") != "bfcl_materialization_classifier_after_decode_debug":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"artifact_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("artifact_route_drift")
    if data.get("no_provider") is not True or data.get("synthetic_fixtures_only") is not True:
        blockers.append("artifact_no_provider_or_synthetic_not_true")
    if not data.get("suspected_materialization_classifier_failure_stage"):
        blockers.append("artifact_suspected_materialization_classifier_failure_stage_missing")
    for key in FALSE_ARTIFACT_KEYS:
        if data.get(key) is not False:
            blockers.append(f"artifact_{key}_not_false:{data.get(key)!r}")
    if data.get("variant_order") != VARIANTS:
        blockers.append(f"artifact_variant_order_invalid:{data.get('variant_order')!r}")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if len(records) != len(VARIANTS):
        blockers.append(f"artifact_record_count_invalid:{len(records)}")
    seen = set()
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            blockers.append(f"artifact_record_{idx}_not_object")
            continue
        variant = record.get("variant")
        if variant not in VARIANTS:
            blockers.append(f"artifact_record_{idx}_variant_invalid:{variant!r}")
        if variant in seen:
            blockers.append(f"artifact_record_{idx}_duplicate_variant:{variant}")
        seen.add(variant)
        if record.get("no_provider") is not True or record.get("synthetic_fixtures_only") is not True:
            blockers.append(f"artifact_record_{idx}_provider_boundary_invalid")
        if not record.get("suspected_materialization_classifier_failure_stage"):
            blockers.append(f"artifact_record_{idx}_suspected_stage_missing")
        if variant == "true_empty_decoded_output" and record.get("decoded_output_nonempty") is not False:
            blockers.append("artifact_true_empty_not_distinguished")
        if variant == "missing_materialized_file_path" and record.get("result_layout_observed_label") != "missing":
            blockers.append("artifact_missing_path_not_distinguished")
        if variant == "post_decode_exception_after_nonempty_decode" and record.get("post_decode_exception_simulated") is not True:
            blockers.append("artifact_post_decode_exception_not_simulated")
    if seen != set(VARIANTS):
        blockers.append("artifact_variant_matrix_incomplete")
    blockers.extend(f"artifact_{item}" for item in _scan(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, artifact_path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    packet = _load(packet_path)
    artifact = _load(artifact_path)
    blockers = validate_packet(packet) + validate_artifact(artifact)
    return {
        "report_scope": "bfcl_materialization_classifier_after_decode_debug_check",
        "packet_path": str(packet_path),
        "artifact_path": str(artifact_path),
        "bfcl_materialization_classifier_after_decode_debug_passed": not blockers,
        "suspected_materialization_classifier_failure_stage": artifact.get("suspected_materialization_classifier_failure_stage"),
        "materialized_result_nonempty": artifact.get("materialized_result_nonempty"),
        "result_layout_match": artifact.get("result_layout_match"),
        "classifier_false_protocol_error_on_nonempty": artifact.get("classifier_false_protocol_error_on_nonempty"),
        "protocol_status_false_error_after_nonempty_decode": artifact.get("protocol_status_false_error_after_nonempty_decode"),
        "blockers": sorted(set(blockers)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--artifact", type=Path, default=DEFAULT_ARTIFACT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "bfcl_materialization_classifier_after_decode_debug_check", "bfcl_materialization_classifier_after_decode_debug_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_materialization_classifier_after_decode_debug_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
