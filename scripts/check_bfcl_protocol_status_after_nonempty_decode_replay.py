#!/usr/bin/env python3
"""Check no-provider protocol-status-after-nonempty-decode replay artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_PACKET = ARTIFACT_ROOT / "bfcl_protocol_status_after_nonempty_decode_replay_packet.json"
DEFAULT_ARTIFACT = ARTIFACT_ROOT / "bfcl_protocol_status_after_nonempty_decode_replay.json"
REPLAY_RUN_ID = "multi_turn_long_context_0"
REQUIRED_FIELDS = [
    "no_provider",
    "compact_labels_only",
    "source_artifact",
    "replay_run_id",
    "decoded_nonempty",
    "materialized_shape_label",
    "protocol_error_indicator_detected",
    "protocol_error_indicator_source_label",
    "classifier_status_replayed",
    "protocol_status_label_replayed",
    "false_protocol_error_on_nonempty_decode",
    "suspected_protocol_status_failure_stage",
    "patch_gate_recommended",
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
)
ALLOWED_STAGES = {
    "protocol_error_indicator_false_positive_on_clean_nonempty_decode",
    "materialization_entry_shape_protocol_error_after_nonempty_decode",
    "protocol_status_classifier_maps_materialized_shape_to_protocol_error",
    "insufficient_compact_labels_needs_live_telemetry",
}
ALLOWED_INDICATOR_SOURCES = {
    "none",
    "explicit_handler_error_phrase",
    "structured_error_key",
    "shape_label_contains_error",
    "explicit_error_or_protocol_error_shape_label",
}
ALLOWED_RAWISH_KEYS = {
    "no_provider",
    "provider_request_authorized",
    "provider_request_executed",
    "source_artifact",
}
FORBIDDEN_KEY_RE = re.compile(r"(raw|prompt|case_content|provider_payload|provider_request_body|provider_response_body|logs?|traces?|model_text|tool_args?|tool_arguments|tool_name|function_name|endpoint|api_key|gold|reference|expected|scorer_diff|candidate_output|secret)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz|" + "boyue" + "richdata|provider " + "payload|raw " + "prompt|raw " + "case|scorer " + "diff|candidate " + "output|endpoint " + "value|api " + "key"), re.IGNORECASE)


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
            if path and path[-1] == "route_model" and value == "gpt-4.1":
                continue
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_protocol_status_after_nonempty_decode_replay_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"packet_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("packet_route_drift")
    if data.get("no_provider_required") is not True or data.get("compact_labels_only") is not True:
        blockers.append("packet_no_provider_or_compact_labels_not_true")
    if data.get("replay_run_id") != REPLAY_RUN_ID:
        blockers.append(f"packet_replay_run_id_invalid:{data.get('replay_run_id')!r}")
    for key in FALSE_PACKET_KEYS:
        if data.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{data.get(key)!r}")
    blockers.extend(f"packet_{item}" for item in _scan(data))
    return sorted(set(blockers))


def validate_artifact(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_protocol_status_after_nonempty_decode_replay":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"artifact_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("artifact_route_drift")
    for field in REQUIRED_FIELDS:
        if field not in data:
            blockers.append(f"required_field_missing:{field}")
    if data.get("no_provider") is not True or data.get("compact_labels_only") is not True:
        blockers.append("artifact_no_provider_or_compact_labels_not_true")
    if data.get("replay_run_id") != REPLAY_RUN_ID:
        blockers.append(f"artifact_replay_run_id_invalid:{data.get('replay_run_id')!r}")
    for key in FALSE_ARTIFACT_KEYS:
        if data.get(key) is not False:
            blockers.append(f"artifact_{key}_not_false:{data.get(key)!r}")
    if data.get("decoded_nonempty") is not True:
        blockers.append(f"decoded_nonempty_not_true:{data.get('decoded_nonempty')!r}")
    if data.get("materialized_shape_label") != "protocol_error_shape":
        blockers.append(f"materialized_shape_label_unexpected:{data.get('materialized_shape_label')!r}")
    if data.get("classifier_status_replayed") != "protocol_error":
        blockers.append(f"classifier_status_replayed_unexpected:{data.get('classifier_status_replayed')!r}")
    if data.get("protocol_status_label_replayed") != "protocol_error":
        blockers.append(f"protocol_status_label_replayed_unexpected:{data.get('protocol_status_label_replayed')!r}")
    if data.get("false_protocol_error_on_nonempty_decode") is not True:
        blockers.append(f"false_protocol_error_on_nonempty_decode_not_true:{data.get('false_protocol_error_on_nonempty_decode')!r}")
    if data.get("suspected_protocol_status_failure_stage") not in ALLOWED_STAGES:
        blockers.append(f"suspected_stage_invalid:{data.get('suspected_protocol_status_failure_stage')!r}")
    if data.get("patch_gate_recommended") is not True:
        blockers.append(f"patch_gate_recommended_not_true:{data.get('patch_gate_recommended')!r}")
    variants = data.get("shape_variant_replay") if isinstance(data.get("shape_variant_replay"), list) else []
    variant_names = {record.get("variant") for record in variants if isinstance(record, dict)}
    for required in (
        "clean_nonempty_decoded_execution_list",
        "ordinary_protocol_label_nonempty_decoded",
        "mixed_nonempty_decode_with_explicit_handler_error_phrase",
        "mixed_nonempty_decode_with_structured_error_key",
        "materialized_protocol_error_shape_label",
    ):
        if required not in variant_names:
            blockers.append(f"variant_missing:{required}")
    for record in variants:
        if not isinstance(record, dict):
            blockers.append("variant_not_object")
            continue
        source = record.get("protocol_error_indicator_source_label")
        if source not in ALLOWED_INDICATOR_SOURCES:
            blockers.append(f"variant_source_invalid:{source!r}")
        if record.get("variant") in {"clean_nonempty_decoded_execution_list", "ordinary_protocol_label_nonempty_decoded"}:
            if record.get("classifier_status_replayed") != "generated":
                blockers.append(f"clean_variant_not_generated:{record.get('variant')}")
            if record.get("false_protocol_error_on_nonempty_decode") is not False:
                blockers.append(f"clean_variant_false_error:{record.get('variant')}")
        if record.get("variant") in {"mixed_nonempty_decode_with_explicit_handler_error_phrase", "mixed_nonempty_decode_with_structured_error_key", "materialized_protocol_error_shape_label"}:
            if record.get("classifier_status_replayed") != "protocol_error":
                blockers.append(f"error_variant_not_protocol_error:{record.get('variant')}")
    blockers.extend(f"artifact_{item}" for item in _scan(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, artifact_path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    packet = _load(packet_path)
    artifact = _load(artifact_path)
    blockers = validate_packet(packet) + validate_artifact(artifact)
    return {
        "report_scope": "bfcl_protocol_status_after_nonempty_decode_replay_check",
        "packet_path": str(packet_path),
        "artifact_path": str(artifact_path),
        "bfcl_protocol_status_after_nonempty_decode_replay_passed": not blockers,
        "suspected_protocol_status_failure_stage": artifact.get("suspected_protocol_status_failure_stage"),
        "patch_gate_recommended": artifact.get("patch_gate_recommended"),
        "false_protocol_error_on_nonempty_decode": artifact.get("false_protocol_error_on_nonempty_decode"),
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
        summary = {"report_scope": "bfcl_protocol_status_after_nonempty_decode_replay_check", "bfcl_protocol_status_after_nonempty_decode_replay_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_protocol_status_after_nonempty_decode_replay_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
