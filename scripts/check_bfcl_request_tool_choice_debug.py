#!/usr/bin/env python3
"""Check BFCL request tool-choice debug packet and artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_request_tool_choice_debug_packet.json")
DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_request_tool_choice_debug.json")
SIGNED_IDS = ["web_search_base_0"]
REQUIRED_FALSE_PACKET = (
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
)
REQUIRED_FALSE_ARTIFACT = (
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
ALLOWED_PATCH_KINDS = {"config_only", "proxy_normalization", "runner_env", "handler_shim", "not_recommended"}
ALLOWED_SURFACES = {"bfcl_measurement_responses_to_chat_tool_choice_normalization", "none"}
FORBIDDEN_KEY_RE = re.compile(r"(raw_(?:prompt|case|provider|payload|log|trace|response|text|tool)|prompt_text|case_content|provider_payload|provider_body|headers|endpoint_value|api_key_value|gold|reference|expected|scorer_diff|candidate_output)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(("s" + "k-" + r"[A-Za-z0-9_-]{16,}|https?://|" + "api" + "cz" + "|" + "boyue" + "richdata|raw prompt|raw case|provider payload|scorer diff|gold/reference/expected|candidate output"), re.IGNORECASE)


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


ALLOWED_COMPACT_FIELD_NAMES = {
    "can_enforce_required_without_raw_case",
    "expected_tool_choice_shape_if_fixed",
}


def _scan(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    for path, value in _walk(data):
        key = path[-1] if path else ""
        if key and key not in ALLOWED_COMPACT_FIELD_NAMES and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_request_tool_choice_debug_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"packet_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("packet_route_drift")
    if data.get("signed_run_ids") != SIGNED_IDS:
        blockers.append(f"packet_signed_run_ids_invalid:{data.get('signed_run_ids')!r}")
    if data.get("compact_only") is not True:
        blockers.append("packet_compact_only_not_true")
    for key in REQUIRED_FALSE_PACKET:
        if data.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{data.get(key)!r}")
    blockers.extend(f"packet_{item}" for item in _scan(data))
    return sorted(set(blockers))


def validate_artifact(data: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if data.get("artifact_kind") != "bfcl_request_tool_choice_debug":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"artifact_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_profile") != "novacode" or data.get("route_model") != "gpt-4.1":
        blockers.append("artifact_route_drift")
    if data.get("signed_run_ids") != SIGNED_IDS:
        blockers.append(f"artifact_signed_run_ids_invalid:{data.get('signed_run_ids')!r}")
    if not data.get("suspected_failure_stage"):
        blockers.append("artifact_suspected_failure_stage_missing")
    for key in REQUIRED_FALSE_ARTIFACT:
        if data.get(key) is not False:
            blockers.append(f"artifact_{key}_not_false:{data.get(key)!r}")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if len(records) != 1:
        blockers.append(f"artifact_record_count_invalid:{len(records)}")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            blockers.append(f"artifact_record_{index}_not_object")
            continue
        if record.get("run_id") != SIGNED_IDS[0]:
            blockers.append(f"artifact_record_{index}_run_id_invalid:{record.get('run_id')!r}")
        if record.get("route_profile") != "novacode" or record.get("route_model") != "gpt-4.1":
            blockers.append(f"artifact_record_{index}_route_drift")
        if not record.get("suspected_failure_stage"):
            blockers.append(f"artifact_record_{index}_suspected_failure_stage_missing")
        if record.get("candidate_patch_kind") not in ALLOWED_PATCH_KINDS:
            blockers.append(f"artifact_record_{index}_candidate_patch_kind_invalid:{record.get('candidate_patch_kind')!r}")
        if record.get("patch_surface_label") not in ALLOWED_SURFACES:
            blockers.append(f"artifact_record_{index}_patch_surface_label_invalid:{record.get('patch_surface_label')!r}")
        if record.get("candidate_patch_kind") != "not_recommended" and data.get("performance_evidence") is not False:
            blockers.append(f"artifact_record_{index}_patch_recommends_with_performance_claim")
    blockers.extend(f"artifact_{item}" for item in _scan(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, artifact_path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    packet = _load(packet_path)
    artifact = _load(artifact_path)
    blockers = validate_packet(packet) + validate_artifact(artifact)
    record = artifact.get("records", [{}])[0] if isinstance(artifact.get("records"), list) and artifact.get("records") else {}
    return {
        "report_scope": "bfcl_request_tool_choice_debug_check",
        "packet_path": str(packet_path),
        "artifact_path": str(artifact_path),
        "bfcl_request_tool_choice_debug_passed": not blockers,
        "tool_choice_none_with_tools_present_confirmed": artifact.get("tool_choice_none_with_tools_present_confirmed"),
        "candidate_patch_kind": record.get("candidate_patch_kind") if isinstance(record, dict) else None,
        "patch_surface_label": record.get("patch_surface_label") if isinstance(record, dict) else None,
        "suspected_failure_stage": artifact.get("suspected_failure_stage"),
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
        summary = {"report_scope": "bfcl_request_tool_choice_debug_check", "bfcl_request_tool_choice_debug_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_request_tool_choice_debug_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
