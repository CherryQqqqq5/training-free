#!/usr/bin/env python3
"""Fail-closed checker for the ABHE temporary trace extraction packet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_temporary_trace_extraction_packet.json")

REQUIRED_FIELDS = {
    "artifact_kind",
    "schema_version",
    "approval_status",
    "authorized",
    "execution_started",
    "target_entry_ids",
    "allowed_output",
    "raw_prompt_allowed",
    "raw_trace_allowed",
    "raw_payload_allowed",
    "raw_case_id_allowed",
    "gold_expected_allowed",
    "scorer_diff_allowed",
    "candidate_output_allowed",
    "performance_evidence",
    "explanatory_evidence_only",
    "trace_cards_do_not_update_archive_status",
}
FALSE_KEYS = {
    "authorized",
    "execution_started",
    "raw_prompt_allowed",
    "raw_trace_allowed",
    "raw_payload_allowed",
    "raw_case_id_allowed",
    "gold_expected_allowed",
    "scorer_diff_allowed",
    "candidate_output_allowed",
    "performance_evidence",
}
EXPECTED_TARGET_ENTRY_IDS = ["state_tracking_v0", "hallucination_abstain_v0"]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def validate_packet(packet: Dict[str, Any]) -> List[str]:
    blockers = []
    missing = sorted(REQUIRED_FIELDS - set(packet))
    if missing:
        blockers.append("trace_packet_required_fields_missing:%s" % ",".join(missing))
        return blockers
    if packet.get("artifact_kind") != "abhe_temporary_trace_extraction_packet":
        blockers.append("trace_packet_artifact_kind_invalid:%r" % packet.get("artifact_kind"))
    if packet.get("schema_version") != "abhe_trace_extraction_packet_v0":
        blockers.append("trace_packet_schema_version_invalid:%r" % packet.get("schema_version"))
    if packet.get("approval_status") not in {"draft", "pending"}:
        blockers.append("trace_packet_approval_status_must_remain_draft_or_pending:%r" % packet.get("approval_status"))
    for key in sorted(FALSE_KEYS):
        if packet.get(key) is not False:
            blockers.append("trace_packet_%s_not_false:%r" % (key, packet.get(key)))
    if packet.get("target_entry_ids") != EXPECTED_TARGET_ENTRY_IDS:
        blockers.append("trace_packet_target_entry_ids_invalid:%r" % packet.get("target_entry_ids"))
    if packet.get("allowed_output") != "sanitized_trace_cards_only":
        blockers.append("trace_packet_allowed_output_invalid:%r" % packet.get("allowed_output"))
    if packet.get("explanatory_evidence_only") is not True:
        blockers.append("trace_packet_explanatory_evidence_only_not_true")
    if packet.get("trace_cards_do_not_update_archive_status") is not True:
        blockers.append("trace_packet_archive_status_guard_not_true")
    blockers.extend(scan_value(packet, label="trace_packet"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_PACKET) -> Dict[str, Any]:
    if not path.exists():
        return {
            "report_scope": "abhe_trace_extraction_packet_check",
            "packet_path": str(path),
            "packet_present": False,
            "abhe_trace_extraction_packet_passed": False,
            "blockers": ["trace_packet_missing"],
        }
    packet = _load(path)
    blockers = validate_packet(packet)
    return {
        "report_scope": "abhe_trace_extraction_packet_check",
        "packet_path": str(path),
        "packet_present": True,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "execution_started": packet.get("execution_started"),
        "performance_evidence": packet.get("performance_evidence"),
        "abhe_trace_extraction_packet_passed": not blockers,
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
        summary = {
            "report_scope": "abhe_trace_extraction_packet_check",
            "abhe_trace_extraction_packet_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_trace_extraction_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
