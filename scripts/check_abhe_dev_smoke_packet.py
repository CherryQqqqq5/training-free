#!/usr/bin/env python3
"""Fail-closed checker for a future ABHE bounded dev smoke packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_bounded_dev_smoke_execution_packet.json")

REQUIRED_FIELDS = {
    "artifact_kind",
    "schema_version",
    "approval_status",
    "authorized",
    "execution_started",
    "entry_ids",
    "baseline_command_template",
    "candidate_command_template",
    "case_list_hash",
    "fresh_dev_slice_source",
    "provider",
    "model",
    "protocol",
    "runtime_config_path",
    "candidate_rule_path",
    "artifact_boundary",
    "cost_latency_cap",
    "regression_cap",
    "stop_loss_criteria",
}
FALSE_KEYS = {
    "authorized",
    "execution_started",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "candidate_generation_authorized",
    "candidate_jsonl_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
}
REQUIRED_STOP_LOSS = {
    "raw_leakage",
    "case_count_exceeds_cap",
    "provider_model_protocol_mismatch",
    "fresh_dev_slice_missing_or_reused",
    "candidate_jsonl_or_pool_created",
    "holdout_or_full_suite_touched",
    "cost_or_latency_cap_exceeded",
    "regression_cap_exceeded",
    "checker_failure",
}
ALLOWED_ENTRY_IDS = ["state_tracking_v0", "hallucination_abstain_v0"]
DISALLOWED_WATCH_ENTRY_IDS = {"unresolved_search_memory_watch_v0"}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def validate_packet(packet: Dict[str, Any]) -> List[str]:
    blockers = []
    missing = sorted(REQUIRED_FIELDS - set(packet))
    if missing:
        blockers.append("packet_required_fields_missing:%s" % ",".join(missing))
        return blockers
    if packet.get("artifact_kind") != "abhe_bounded_dev_smoke_execution_packet":
        blockers.append("packet_artifact_kind_invalid:%r" % packet.get("artifact_kind"))
    if packet.get("schema_version") != "abhe_dev_smoke_packet_v0":
        blockers.append("packet_schema_version_invalid:%r" % packet.get("schema_version"))
    if packet.get("approval_status") not in {"pending", "draft"}:
        blockers.append("packet_approval_status_must_remain_pending_or_draft:%r" % packet.get("approval_status"))
    for key in sorted(FALSE_KEYS):
        if packet.get(key) is not False:
            blockers.append("packet_%s_not_false:%r" % (key, packet.get(key)))
    entry_ids = packet.get("entry_ids")
    if not isinstance(entry_ids, list) or not entry_ids:
        blockers.append("packet_entry_ids_empty")
    elif entry_ids != ALLOWED_ENTRY_IDS:
        blockers.append("packet_entry_ids_must_match_proposal_ready_entries:%r" % entry_ids)
    if isinstance(entry_ids, list):
        disallowed = sorted(DISALLOWED_WATCH_ENTRY_IDS.intersection(set(entry_ids)))
        if disallowed:
            blockers.append("packet_watch_entries_must_not_enter_dev_smoke:%s" % ",".join(disallowed))
    if not packet.get("fresh_dev_slice_source"):
        blockers.append("packet_fresh_dev_slice_source_empty")
    stop_loss = set(packet.get("stop_loss_criteria") or [])
    missing_stop_loss = sorted(REQUIRED_STOP_LOSS - stop_loss)
    if missing_stop_loss:
        blockers.append("packet_stop_loss_missing:%s" % ",".join(missing_stop_loss))
    boundary = packet.get("artifact_boundary")
    if not isinstance(boundary, dict):
        blockers.append("packet_artifact_boundary_not_object")
    else:
        if boundary.get("compact_only") is not True:
            blockers.append("packet_artifact_boundary_compact_only_not_true")
        if boundary.get("raw_outputs_committed") is not False:
            blockers.append("packet_artifact_boundary_raw_outputs_committed_not_false")
        if boundary.get("forbidden_fields_absent_required") is not True:
            blockers.append("packet_artifact_boundary_forbidden_fields_absent_required_not_true")
    blockers.extend(scan_value(packet, label="packet"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> Dict[str, Any]:
    if not path.exists():
        return {
            "report_scope": "abhe_dev_smoke_packet_check",
            "packet_path": str(path),
            "abhe_dev_smoke_packet_passed": False,
            "packet_present": False,
            "blockers": ["packet_missing_pending_request_not_created"],
        }
    packet = _load(path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "abhe_dev_smoke_packet_check",
        "packet_path": str(path),
        "packet_present": True,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "execution_started": packet.get("execution_started"),
        "performance_evidence": packet.get("performance_evidence"),
        "abhe_dev_smoke_packet_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {"report_scope": "abhe_dev_smoke_packet_check", "abhe_dev_smoke_packet_passed": False, "blockers": ["load_failed:%s" % exc]}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_dev_smoke_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
