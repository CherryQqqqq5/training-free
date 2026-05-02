#!/usr/bin/env python3
"""Check no-provider BFCL exact request shape capture packet and artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_request_shape_capture_packet.json")
DEFAULT_ARTIFACT = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_request_shape_capture.json")
SIGNED_IDS = ["web_search_base_0", "multi_turn_base_0"]
REQUIRED_FALSE_PACKET = (
    "authorized",
    "provider_request_authorized",
    "bfcl_smoke_authorized",
    "bfcl_scorer_authorized",
    "full_baseline_authorized",
    "candidate_runtime_activation_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "provider_request_executed",
    "bfcl_smoke_executed",
    "scorer_executed",
    "full_baseline_executed",
    "endpoint_value_committed",
    "api_key_value_committed",
    "raw_material_persisted",
)
REQUIRED_FALSE_ARTIFACT = (
    "provider_request_executed",
    "bfcl_smoke_executed",
    "scorer_executed",
    "full_baseline_executed",
    "candidate_runtime_activation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "raw_prompt_persisted",
    "raw_case_content_persisted",
    "raw_provider_payload_persisted",
    "raw_log_persisted",
    "raw_trace_persisted",
    "endpoint_or_key_committed",
)
ALLOWED_FALSE_KEYS = set(REQUIRED_FALSE_PACKET) | set(REQUIRED_FALSE_ARTIFACT) | {"missing_tool_choice_confirmed", "missing_token_limit_confirmed"}
FORBIDDEN_KEY_RE = re.compile(r"(raw_(?:prompt|case|provider|payload|log|trace|response)|case_id|gold|reference|expected|scorer_diff|candidate_output|endpoint_value|api_key_value)", re.IGNORECASE)
FORBIDDEN_VALUE_RE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|https?://|raw prompt|raw case|provider payload|scorer diff|gold/reference/expected|candidate output)", re.IGNORECASE)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain object")
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
        if path:
            key = path[-1]
            if FORBIDDEN_KEY_RE.search(key) and key not in ALLOWED_FALSE_KEYS:
                blockers.append(f"forbidden_key:{'.'.join(path)}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            blockers.append(f"forbidden_value:{'.'.join(path)}")
    return sorted(set(blockers))


def validate_packet(data: dict[str, Any]) -> list[str]:
    blockers = []
    if data.get("artifact_kind") != "bfcl_exact_request_shape_capture_packet":
        blockers.append(f"packet_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("approval_status") != "prepared":
        blockers.append(f"packet_approval_status_invalid:{data.get('approval_status')!r}")
    if data.get("route_model") != "gpt-4.1" or data.get("active_profile") != "novacode":
        blockers.append("packet_route_drift")
    for key in REQUIRED_FALSE_PACKET:
        if data.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{data.get(key)!r}")
    for key in ("candidate_specs_inert", "endpoint_env_only", "api_key_env_only", "compact_shape_only"):
        if data.get(key) is not True:
            blockers.append(f"packet_{key}_not_true:{data.get(key)!r}")
    if data.get("signed_run_ids") != SIGNED_IDS:
        blockers.append(f"packet_signed_run_ids_invalid:{data.get('signed_run_ids')!r}")
    blockers.extend(f"packet_{item}" for item in _scan(data))
    return sorted(set(blockers))


def validate_artifact(data: dict[str, Any]) -> list[str]:
    blockers = []
    if data.get("artifact_kind") != "bfcl_exact_request_shape_capture":
        blockers.append(f"artifact_kind_invalid:{data.get('artifact_kind')!r}")
    if data.get("route_model") != "gpt-4.1" or data.get("active_profile") != "novacode":
        blockers.append("artifact_route_drift")
    for key in REQUIRED_FALSE_ARTIFACT:
        if data.get(key) is not False:
            blockers.append(f"artifact_{key}_not_false:{data.get(key)!r}")
    if not data.get("suspected_exact_request_gap"):
        blockers.append("artifact_suspected_exact_request_gap_missing")
    ids = data.get("signed_run_ids") if isinstance(data.get("signed_run_ids"), list) else []
    if ids != SIGNED_IDS:
        blockers.append(f"artifact_signed_run_ids_invalid:{ids!r}")
    records = data.get("records") if isinstance(data.get("records"), list) else []
    if not records:
        blockers.append("artifact_records_missing")
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            blockers.append(f"artifact_record_{index}_not_object")
            continue
        run_id = record.get("run_id_label")
        if run_id not in SIGNED_IDS:
            blockers.append(f"artifact_record_{index}_unsigned_run_id:{run_id!r}")
        if record.get("provider_request_executed") is not False or record.get("no_provider_request_executed") is not True:
            blockers.append(f"artifact_record_{index}_provider_execution_flag_invalid")
        if not record.get("suspected_exact_request_gap"):
            blockers.append(f"artifact_record_{index}_suspected_gap_missing")
    blockers.extend(f"artifact_{item}" for item in _scan(data))
    return sorted(set(blockers))


def check(packet_path: Path = DEFAULT_PACKET, artifact_path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    packet = _load(packet_path)
    artifact = _load(artifact_path)
    blockers = validate_packet(packet) + validate_artifact(artifact)
    return {
        "report_scope": "bfcl_exact_request_shape_capture_check",
        "packet_path": str(packet_path),
        "artifact_path": str(artifact_path),
        "bfcl_exact_request_shape_capture_passed": not blockers,
        "suspected_exact_request_gap": artifact.get("suspected_exact_request_gap"),
        "missing_tool_choice_confirmed": artifact.get("missing_tool_choice_confirmed"),
        "missing_token_limit_confirmed": artifact.get("missing_token_limit_confirmed"),
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
        summary = {"report_scope": "bfcl_exact_request_shape_capture_check", "bfcl_exact_request_shape_capture_passed": False, "blockers": [f"load_failed:{exc}"]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["bfcl_exact_request_shape_capture_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
