#!/usr/bin/env python3
"""Validate optional ABHE sanitized trace cards without extracting traces."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_card.schema.json")
DEFAULT_CARDS = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_cards.json")

CARD_REQUIRED_FIELDS = {
    "trace_card_id",
    "source_hash",
    "entry_id",
    "behavior_cluster",
    "observed_failure_pattern",
    "turn_span_summary",
    "allowed_compact_evidence",
    "forbidden_fields_absent",
}
CARD_ALLOWED_FIELDS = CARD_REQUIRED_FIELDS | {"state_variable_lost", "answerability_failure_kind"}
ALLOWED_ENTRY_IDS = {"state_tracking_v0", "hallucination_abstain_v0"}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_schema(schema: Dict[str, Any]) -> List[str]:
    blockers = []
    if schema.get("type") != "object":
        blockers.append("trace_card_schema_type_must_be_object")
    if schema.get("additionalProperties") is not False:
        blockers.append("trace_card_schema_additional_properties_must_be_false")
    if set(schema.get("required") or []) != CARD_REQUIRED_FIELDS:
        blockers.append("trace_card_schema_required_fields_mismatch")
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        blockers.append("trace_card_schema_properties_missing")
        return blockers
    missing = sorted(CARD_ALLOWED_FIELDS - set(properties))
    if missing:
        blockers.append("trace_card_schema_properties_missing:%s" % ",".join(missing))
    forbidden_absent = properties.get("forbidden_fields_absent")
    if not isinstance(forbidden_absent, dict) or forbidden_absent.get("const") is not True:
        blockers.append("trace_card_schema_forbidden_fields_absent_const_invalid")
    blockers.extend(scan_value(schema, label="trace_card_schema"))
    return sorted(set(blockers))


def _extract_cards(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        cards = data
    elif isinstance(data, dict) and isinstance(data.get("cards"), list):
        cards = data["cards"]
    else:
        raise ValueError("trace cards must be a JSON array or an object with cards[]")
    if not all(isinstance(card, dict) for card in cards):
        raise ValueError("each trace card must be a JSON object")
    return cards


def validate_card(card: Dict[str, Any], label: str) -> List[str]:
    blockers = []
    missing = sorted(CARD_REQUIRED_FIELDS - set(card))
    if missing:
        blockers.append("%s_missing_fields:%s" % (label, ",".join(missing)))
        return blockers
    extra = sorted(set(card) - CARD_ALLOWED_FIELDS)
    if extra:
        blockers.append("%s_extra_fields:%s" % (label, ",".join(extra)))
    if card.get("entry_id") not in ALLOWED_ENTRY_IDS:
        blockers.append("%s_entry_id_invalid:%r" % (label, card.get("entry_id")))
    if card.get("forbidden_fields_absent") is not True:
        blockers.append("%s_forbidden_fields_absent_not_true:%r" % (label, card.get("forbidden_fields_absent")))
    if not isinstance(card.get("allowed_compact_evidence"), list):
        blockers.append("%s_allowed_compact_evidence_not_list" % label)
    if card.get("entry_id") == "state_tracking_v0" and not card.get("state_variable_lost"):
        blockers.append("%s_state_variable_lost_required_for_state_tracking" % label)
    if card.get("entry_id") == "hallucination_abstain_v0" and not card.get("answerability_failure_kind"):
        blockers.append("%s_answerability_failure_kind_required_for_hallucination_abstain" % label)
    blockers.extend(scan_value(card, label=label))
    return sorted(set(blockers))


def check(
    schema_path: Path = DEFAULT_SCHEMA,
    cards_path: Path = DEFAULT_CARDS,
    require_cards: bool = False,
) -> Dict[str, Any]:
    blockers = []
    schema = _load(schema_path)
    if not isinstance(schema, dict):
        raise ValueError("%s must contain a JSON object" % schema_path)
    blockers.extend(validate_schema(schema))
    cards_present = cards_path.exists()
    card_count = 0
    if cards_present:
        data = _load(cards_path)
        cards = _extract_cards(data)
        card_count = len(cards)
        for index, card in enumerate(cards):
            blockers.extend(validate_card(card, "trace_card_%d" % index))
    elif require_cards:
        blockers.append("trace_cards_missing")
    return {
        "report_scope": "abhe_trace_cards_check",
        "schema_path": str(schema_path),
        "cards_path": str(cards_path),
        "trace_cards_present": cards_present,
        "trace_card_count": card_count,
        "performance_evidence": False,
        "raw_material_absent_required": True,
        "abhe_trace_cards_check_passed": not blockers,
        "blockers": sorted(set(blockers)),
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--cards", type=Path, default=DEFAULT_CARDS)
    parser.add_argument("--require-cards", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.schema, args.cards, args.require_cards)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "abhe_trace_cards_check",
            "abhe_trace_cards_check_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["abhe_trace_cards_check_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
