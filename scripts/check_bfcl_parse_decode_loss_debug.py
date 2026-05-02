#!/usr/bin/env python3
"""Check Stage 1F no-provider BFCL parse/decode-loss debug packet and artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_PACKET = ARTIFACT_ROOT / "bfcl_parse_decode_loss_debug_packet.json"
DEFAULT_ARTIFACT = ARTIFACT_ROOT / "bfcl_parse_decode_loss_debug.json"
RUN_ID = "web_search_base_0"
VARIANT_ORDER = [
    "valid_json_string_arguments_completed_status",
    "valid_object_arguments_completed_status",
    "missing_call_id",
    "missing_status",
    "missing_name",
    "missing_arguments",
    "name_nested_under_function",
    "arguments_nested_under_function",
    "invalid_json_string_arguments",
    "status_in_progress",
]
FALSE_PACKET_KEYS = (
    "authorized",
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
    "gpt_4o_fallback_allowed",
    "gpt_5_2_active",
    "openrouter_allowed",
)
FALSE_ARTIFACT_KEYS = (
    "provider_request_executed",
    "live_telemetry_executed",
    "bfcl_generate_executed",
    "bfcl_smoke_executed",
    "bfcl_evaluate_executed",
    "scorer_executed",
    "full_baseline_executed",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "fallback_allowed",
    "gpt_4o_fallback_allowed",
    "gpt_5_2_active",
    "openrouter_allowed",
)
ALLOWED_RAWISH_KEYS = {
    "api_key_env_only",
    "api_key_value_committed",
    "bfcl_parser_expected_shape_label",
    "endpoint_env_only",
    "endpoint_value_committed",
    "no_bfcl_case_content",
    "no_provider",
    "raw_bfcl_case_content_allowed",
    "raw_logs_allowed",
    "raw_provider_payload_allowed",
    "raw_tool_arguments_allowed",
    "target_observed_artifact",
}
FORBIDDEN_KEY_RE = re.compile(r"(raw_(?:prompt|case|provider|payload|log|trace|response|text|tool_args?)|prompt_text|case_content|provider_payload|provider_body|headers|endpoint_value|api_key_value|gold|reference|expected|scorer_diff|candidate_output)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|" + "api" + "cz" + "|" + "boyue" + "richdata|raw prompt|raw case|provider payload|scorer diff|gold/reference/expected|candidate output|endpoint value|api key"), re.IGNORECASE)


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


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_parse_decode_loss_debug_packet":
        blockers.append(f"packet_artifact_kind_invalid:{data.get('artifact_kind')!r}")
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
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_parse_decode_loss_debug":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"artifact_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("artifact_route_drift")
    if data.get("run_id") != RUN_ID:
        blockers.append(f"artifact_run_id_invalid:{data.get('run_id')!r}")
    if data.get("no_provider") is not True:
        blockers.append(f"artifact_no_provider_not_true:{data.get('no_provider')!r}")
    if data.get("synthetic_fixtures_only") is not True:
        blockers.append(f"artifact_synthetic_fixtures_only_not_true:{data.get('synthetic_fixtures_only')!r}")
    if not data.get("suspected_parse_decode_failure_stage"):
        blockers.append("artifact_suspected_parse_decode_failure_stage_missing")
    for key in FALSE_ARTIFACT_KEYS:
        if data.get(key) is not False:
            blockers.append(f"artifact_{key}_not_false:{data.get(key)!r}")
    if data.get("variant_order") != VARIANT_ORDER:
        blockers.append(f"artifact_variant_order_invalid:{data.get('variant_order')!r}")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if len(records) != len(VARIANT_ORDER):
        blockers.append(f"artifact_record_count_invalid:{len(records)}")
    seen: set[str] = set()
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            blockers.append(f"artifact_record_{index}_not_object")
            continue
        variant = str(record.get("variant"))
        if variant not in VARIANT_ORDER:
            blockers.append(f"artifact_record_{index}_variant_invalid:{variant!r}")
        if variant in seen:
            blockers.append(f"artifact_record_{index}_variant_duplicate:{variant}")
        seen.add(variant)
        if record.get("no_provider") is not True or record.get("synthetic_fixtures_only") is not True:
            blockers.append(f"artifact_record_{index}_provider_or_synthetic_boundary_invalid")
        if not record.get("suspected_parse_decode_failure_stage"):
            blockers.append(f"artifact_record_{index}_suspected_stage_missing")
        if variant.startswith("valid_") and record.get("decode_execute_called") is not True and data.get("handler_import_available") is True:
            blockers.append(f"artifact_record_{index}_valid_variant_decode_not_called")
        if variant == "missing_call_id" and "call_id" not in set(record.get("missing_required_decode_fields") or []):
            blockers.append("artifact_missing_call_id_variant_not_classified")
        if variant == "missing_status" and record.get("proxy_responses_function_call_has_status") is not False:
            blockers.append("artifact_missing_status_variant_not_classified")
        if variant == "missing_name" and "name" not in set(record.get("missing_required_decode_fields") or []):
            blockers.append("artifact_missing_name_variant_not_classified")
        if variant == "missing_arguments" and "arguments" not in set(record.get("missing_required_decode_fields") or []):
            blockers.append("artifact_missing_arguments_variant_not_classified")
    if seen != set(VARIANT_ORDER):
        blockers.append("artifact_variant_matrix_incomplete")
    blockers.extend(f"artifact_{item}" for item in _scan(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, artifact_path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    packet = _load(packet_path)
    artifact = _load(artifact_path)
    blockers = validate_packet(packet) + validate_artifact(artifact)
    return {
        "report_scope": "bfcl_parse_decode_loss_debug_check",
        "packet_path": str(packet_path),
        "artifact_path": str(artifact_path),
        "bfcl_parse_decode_loss_debug_passed": not blockers,
        "handler_import_available": artifact.get("handler_import_available"),
        "responses_handler_available": artifact.get("responses_handler_available"),
        "decode_execute_called": artifact.get("decode_execute_called"),
        "decode_execute_nonempty": artifact.get("decode_execute_nonempty"),
        "shape_mismatch_detected": artifact.get("shape_mismatch_detected"),
        "suspected_parse_decode_failure_stage": artifact.get("suspected_parse_decode_failure_stage"),
        "next_recommended_patch_gate": artifact.get("next_recommended_patch_gate"),
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
        summary = {"report_scope": "bfcl_parse_decode_loss_debug_check", "bfcl_parse_decode_loss_debug_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_parse_decode_loss_debug_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
