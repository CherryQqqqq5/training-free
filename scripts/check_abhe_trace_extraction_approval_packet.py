#!/usr/bin/env python3
"""Check a future trace extraction approval packet; default missing packet is fail-closed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_extraction_approval.schema.json")
DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_extraction_approval_packet.json")
REQUIRED_FIELDS = {
    "approval_status",
    "authorized",
    "review_owner",
    "approved_output_path",
    "approved_max_trace_card_count",
    "approved_target_entry_ids",
    "approval_scope",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "candidate_generation_authorized",
    "performance_evidence",
}
FALSE_KEYS = {
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "scorer_authorized",
    "candidate_generation_authorized",
    "performance_evidence",
}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def validate_schema(schema: Dict[str, Any]) -> List[str]:
    blockers = []
    if schema.get("type") != "object":
        blockers.append("trace_extraction_approval_schema_type_must_be_object")
    if schema.get("additionalProperties") is not False:
        blockers.append("trace_extraction_approval_schema_additional_properties_must_be_false")
    if set(schema.get("required") or []) != REQUIRED_FIELDS:
        blockers.append("trace_extraction_approval_schema_required_fields_mismatch")
    props = schema.get("properties")
    if not isinstance(props, dict):
        blockers.append("trace_extraction_approval_schema_properties_missing")
        return blockers
    missing = sorted(REQUIRED_FIELDS - set(props))
    if missing:
        blockers.append("trace_extraction_approval_schema_properties_missing:%s" % ",".join(missing))
    consts: Dict[str, Any] = {
        "approval_status": "approved",
        "authorized": True,
        "approval_scope": "trace_cards_only",
    }
    consts.update({key: False for key in FALSE_KEYS})
    for key, expected in consts.items():
        if not isinstance(props.get(key), dict) or props[key].get("const") != expected:
            blockers.append("trace_extraction_approval_schema_%s_const_invalid:%r" % (key, props.get(key)))
    blockers.extend(scan_value(schema, label="trace_extraction_approval_schema"))
    return sorted(set(blockers))


def validate_packet(packet: Dict[str, Any]) -> List[str]:
    blockers = []
    missing = sorted(REQUIRED_FIELDS - set(packet))
    if missing:
        blockers.append("trace_extraction_approval_packet_required_fields_missing:%s" % ",".join(missing))
        return blockers
    if packet.get("approval_status") != "approved":
        blockers.append("trace_extraction_approval_packet_status_not_approved:%r" % packet.get("approval_status"))
    if packet.get("authorized") is not True:
        blockers.append("trace_extraction_approval_packet_authorized_not_true:%r" % packet.get("authorized"))
    if packet.get("approval_scope") != "trace_cards_only":
        blockers.append("trace_extraction_approval_packet_scope_invalid:%r" % packet.get("approval_scope"))
    for key in sorted(FALSE_KEYS):
        if packet.get(key) is not False:
            blockers.append("trace_extraction_approval_packet_%s_not_false:%r" % (key, packet.get(key)))
    blockers.extend(scan_value(packet, label="trace_extraction_approval_packet"))
    return sorted(set(blockers))


def check(schema_path: Path = DEFAULT_SCHEMA, packet_path: Path = DEFAULT_PACKET) -> Dict[str, Any]:
    schema = _load(schema_path)
    schema_blockers = validate_schema(schema)
    if not packet_path.exists():
        return {
            "report_scope": "abhe_trace_extraction_approval_packet_check",
            "schema_path": str(schema_path),
            "packet_path": str(packet_path),
            "schema_passed": not schema_blockers,
            "packet_present": False,
            "abhe_trace_extraction_approval_packet_passed": False,
            "blockers": sorted(set(schema_blockers + ["trace_extraction_approval_packet_missing"])),
        }
    packet = _load(packet_path)
    blockers = schema_blockers + validate_packet(packet)
    return {
        "report_scope": "abhe_trace_extraction_approval_packet_check",
        "schema_path": str(schema_path),
        "packet_path": str(packet_path),
        "schema_passed": not schema_blockers,
        "packet_present": True,
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "approval_scope": packet.get("approval_scope"),
        "abhe_trace_extraction_approval_packet_passed": not blockers,
        "blockers": sorted(set(blockers)),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.schema, args.packet)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "abhe_trace_extraction_approval_packet_check",
            "abhe_trace_extraction_approval_packet_passed": False,
            "schema_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_trace_extraction_approval_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
