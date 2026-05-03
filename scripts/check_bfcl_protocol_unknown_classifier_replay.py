#!/usr/bin/env python3
"""Check no-provider protocol/unknown classifier replay artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_PACKET = ARTIFACT_ROOT / "bfcl_protocol_unknown_classifier_replay_packet.json"
DEFAULT_ARTIFACT = ARTIFACT_ROOT / "bfcl_protocol_unknown_classifier_replay.json"
TARGET_PROTOCOL_ID = "multi_turn_long_context_0"
TARGET_UNKNOWN_IDS = ["irrelevance_0", "live_irrelevance_0-0-0"]
FALSE_KEYS = (
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
EXEC_FALSE_KEYS = (
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
ALLOWED_RAWISH_KEYS = {
    "no_provider",
    "provider_request_authorized",
    "provider_request_executed",
    "source_artifact",
    "source_smoke_artifact",
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
    if data.get("artifact_kind") != "bfcl_protocol_unknown_classifier_replay_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"packet_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("packet_route_drift")
    if data.get("no_provider_required") is not True or data.get("synthetic_or_compact_labels_only") is not True:
        blockers.append("packet_no_provider_or_compact_labels_not_true")
    for key in FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{data.get(key)!r}")
    blockers.extend(f"packet_{item}" for item in _scan(data))
    return sorted(set(blockers))


def validate_artifact(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_protocol_unknown_classifier_replay":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"artifact_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("artifact_route_drift")
    if data.get("no_provider") is not True or data.get("compact_artifact_labels_only") is not True:
        blockers.append("artifact_no_provider_or_compact_labels_not_true")
    if not data.get("suspected_classifier_replay_stage"):
        blockers.append("artifact_suspected_classifier_replay_stage_missing")
    for key in EXEC_FALSE_KEYS:
        if data.get(key) is not False:
            blockers.append(f"artifact_{key}_not_false:{data.get(key)!r}")
    if data.get("target_protocol_run_id") != TARGET_PROTOCOL_ID:
        blockers.append(f"target_protocol_run_id_invalid:{data.get('target_protocol_run_id')!r}")
    if data.get("target_unknown_run_ids") != TARGET_UNKNOWN_IDS:
        blockers.append(f"target_unknown_run_ids_invalid:{data.get('target_unknown_run_ids')!r}")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    by_id = {record.get("run_id"): record for record in records if isinstance(record, dict)}
    if TARGET_PROTOCOL_ID not in by_id:
        blockers.append("target_protocol_record_missing")
    else:
        record = by_id[TARGET_PROTOCOL_ID]
        if record.get("compact_status") != "protocol_error" or record.get("protocol_error_detected") is not True:
            blockers.append("target_protocol_record_not_protocol_error")
    for run_id in TARGET_UNKNOWN_IDS:
        record = by_id.get(run_id)
        if not record:
            blockers.append(f"unknown_record_missing:{run_id}")
            continue
        if record.get("compact_status") != "unknown_compact_status":
            blockers.append(f"unknown_record_status_invalid:{run_id}:{record.get('compact_status')!r}")
        if record.get("compact_shape_data_sufficient_for_root_cause") is not False:
            blockers.append(f"unknown_record_not_marked_limited:{run_id}")
    blockers.extend(f"artifact_{item}" for item in _scan(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, artifact_path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    packet = _load(packet_path)
    artifact = _load(artifact_path)
    blockers = validate_packet(packet) + validate_artifact(artifact)
    return {
        "report_scope": "bfcl_protocol_unknown_classifier_replay_check",
        "packet_path": str(packet_path),
        "artifact_path": str(artifact_path),
        "bfcl_protocol_unknown_classifier_replay_passed": not blockers,
        "classifier_replay_feasible": artifact.get("classifier_replay_feasible"),
        "protocol_error_replay_label": artifact.get("protocol_error_replay_label"),
        "unknown_root_cause_resolved_by_compact_replay": artifact.get("unknown_root_cause_resolved_by_compact_replay"),
        "suspected_classifier_replay_stage": artifact.get("suspected_classifier_replay_stage"),
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
        summary = {"report_scope": "bfcl_protocol_unknown_classifier_replay_check", "bfcl_protocol_unknown_classifier_replay_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("bfcl_protocol_unknown_classifier_replay_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
