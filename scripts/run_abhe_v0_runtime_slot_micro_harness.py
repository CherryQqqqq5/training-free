#!/usr/bin/env python3
"""Run synthetic compact micro-harness for ABHE runtime slot controller v2."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.abhe_v0_runtime_slot_controller import runtime_slot_controller_v2

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
OUT = ROOT / "abhe_v0_runtime_slot_micro_harness.json"


def _tool(name: str, required: List[str], types: Dict[str, str] | None = None) -> Dict[str, Any]:
    types = types or {slot: "string" for slot in required}
    return {
        "type": "function",
        "function": {
            "name": name,
            "parameters": {
                "type": "object",
                "properties": {slot: {"type": types.get(slot, "string")} for slot in required},
                "required": required,
            },
        },
    }


def _hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fixtures() -> List[Dict[str, Any]]:
    fixtures: List[Dict[str, Any]] = []
    base_tool = _tool("book", ["city", "date", "party_size"], {"city": "string", "date": "string", "party_size": "integer"})
    lookup_tool = _tool("lookup_city", ["landmark"])
    for i in range(10):
        fixtures.append({"group": "schema_reader", "tool": base_tool, "tool_call": {"name": "book", "arguments": {}}, "sources": [], "available_tools": [], "recoverability_map": {}, "expected_decision": "ask_or_insufficient", "expected_required_arg_count": 3})
    for i in range(10):
        fixtures.append({"group": "valid_tool_call_guard", "tool": base_tool, "tool_call": {"name": "book", "arguments": {"city": "known_city", "date": "known_date", "party_size": 2}}, "sources": [], "available_tools": [], "recoverability_map": {}, "expected_decision": "allow_valid_tool_call", "expect_block_valid": False})
    for i in range(10):
        source_type = "prior_tool_observation" if i % 2 else "prior_confirmed_selection"
        fixtures.append({"group": "slot_binder", "tool": base_tool, "tool_call": {"name": "book", "arguments": {"city": "known_city", "date": "known_date"}}, "sources": [{"source_type": source_type, "values": {"party_size": 2}}], "available_tools": [], "recoverability_map": {}, "expected_decision": "bind_recovered_slots_then_call", "expected_bindable_count": 1})
    for i in range(10):
        fixtures.append({"group": "lookup_planner", "tool": base_tool, "tool_call": {"name": "book", "arguments": {"date": "known_date", "party_size": 2}}, "sources": [], "available_tools": [lookup_tool], "recoverability_map": {"city": "lookup_city"}, "expected_decision": "call_prerequisite_lookup", "expected_lookup_needed_count": 1})
    for i in range(5):
        fixtures.append({"group": "ambiguity_control", "tool": base_tool, "tool_call": {"name": "book", "arguments": {"date": "known_date", "party_size": 2}}, "sources": [{"source_type": "prior_confirmed_selection", "values": {"city": "a"}}, {"source_type": "prior_tool_observation", "values": {"city": "b"}}], "available_tools": [], "recoverability_map": {}, "expected_decision": "ask_or_insufficient_due_ambiguity", "expected_ambiguity": True})
    for i in range(5):
        fixtures.append({"group": "unrecoverable_control", "tool": base_tool, "tool_call": {"name": "book", "arguments": {"city": "known_city", "date": "known_date"}}, "sources": [], "available_tools": [], "recoverability_map": {}, "expected_decision": "ask_or_insufficient"})
    return fixtures


def build() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    summary: Dict[str, Dict[str, int]] = {}
    blockers: List[str] = []
    for idx, fixture in enumerate(_fixtures()):
        result = runtime_slot_controller_v2(fixture["tool"], fixture["tool_call"], fixture["sources"], fixture["available_tools"], fixture["recoverability_map"])
        group = fixture["group"]
        bucket = summary.setdefault(group, {"fixture_count": 0, "passed_count": 0, "failed_count": 0})
        bucket["fixture_count"] += 1
        passed = result["decision"] == fixture["expected_decision"]
        if "expected_required_arg_count" in fixture:
            passed = passed and result["schema_reader"]["required_arg_count"] == fixture["expected_required_arg_count"]
        if "expect_block_valid" in fixture:
            passed = passed and result["would_block_valid_tool_call"] is fixture["expect_block_valid"]
        if "expected_bindable_count" in fixture:
            binder = result.get("slot_binder") or {}
            passed = passed and binder.get("bindable_count") == fixture["expected_bindable_count"]
        if "expected_lookup_needed_count" in fixture:
            planner = result.get("lookup_planner") or {}
            passed = passed and planner.get("lookup_needed_count") == fixture["expected_lookup_needed_count"]
        if "expected_ambiguity" in fixture:
            binder = result.get("slot_binder") or {}
            passed = passed and binder.get("entity_ambiguity_detected") is fixture["expected_ambiguity"]
        bucket["passed_count" if passed else "failed_count"] += 1
        if not passed:
            blockers.append(f"fixture_failed:{group}:{idx}")
        rows.append({
            "fixture_hash": _hash(f"{group}:{idx}"),
            "group": group,
            "decision": result["decision"],
            "passed": passed,
            "required_arg_count": result["schema_reader"]["required_arg_count"],
            "missing_required_arg_count": len(result["valid_tool_call_guard"].get("missing_required_args") or []),
            "bindable_count": (result.get("slot_binder") or {}).get("bindable_count", 0),
            "lookup_needed_count": (result.get("lookup_planner") or {}).get("lookup_needed_count", 0),
            "would_block_valid_tool_call": result["would_block_valid_tool_call"],
            "raw_material_absent": True,
        })
    return {
        "artifact_kind": "abhe_v0_runtime_slot_micro_harness",
        "schema_version": "abhe_v0_runtime_slot_micro_harness_v0",
        "fixture_count": len(rows),
        "summary_by_group": summary,
        "rows": rows,
        "micro_harness_passed": not blockers,
        "blockers": blockers,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "raw_material_absent": True,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = build()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True) if args.compact else json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and report["blockers"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
