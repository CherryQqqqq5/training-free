#!/usr/bin/env python3
"""Build ABHE runtime-slot observability fixture review artifact."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from scripts.check_abhe_v0_runtime_slot_observability_fixture import check as check_fixture
from scripts.check_abhe_v0_runtime_slot_observability_plan import check as check_plan

OUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_review.json")


def build() -> Dict[str, Any]:
    fixture = check_fixture()
    plan = check_plan()
    review_passed = fixture.get("observability_fixture_check_passed") is True and plan.get("observability_plan_check_passed") is True
    blockers = []
    if not plan.get("observability_plan_check_passed"):
        blockers.extend(f"plan:{item}" for item in plan.get("blockers", []))
    if not fixture.get("observability_fixture_check_passed"):
        blockers.extend(f"fixture:{item}" for item in fixture.get("blockers", []))
    return {
        "artifact_kind": "abhe_v0_runtime_slot_observability_review",
        "schema_version": "abhe_v0_runtime_slot_observability_review_v0",
        "review_status": "passed" if review_passed else "blocked",
        "authorized": False,
        "review_is_execution_approval": False,
        "bfcl_rerun_authorized": False,
        "provider_calls_authorized": False,
        "provider_calls_made": False,
        "bfcl_generate_authorized": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_authorized": False,
        "bfcl_evaluate_called": False,
        "scorer_authorized": False,
        "scorer_called": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "performance_evidence": False,
        "candidate_jsonl_generated": False,
        "candidate_yaml_generated": False,
        "candidate_rule_generated": False,
        "raw_material_absent": True,
        "safe_fields_only": True,
        "reviewed_artifacts": {
            "observability_plan": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_plan.json",
            "observability_fixture": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_fixture.json",
            "bindability_audit": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_bindability_audit_v1.json",
        },
        "review_findings": {
            "observability_plan_check_passed": plan.get("observability_plan_check_passed") is True,
            "observability_fixture_check_passed": fixture.get("observability_fixture_check_passed") is True,
            "fixture_count": fixture.get("fixture_count"),
            "bind_repair_rows": fixture.get("bind_repair_rows"),
            "provider_generated_valid_call_proxy_rows": fixture.get("provider_generated_valid_call_proxy_rows"),
            "no_tool_final_response_rows": fixture.get("no_tool_final_response_rows"),
            "compact_attribution_surfaces_present": review_passed,
            "direct_slot_binding_causality_for_prior_bfcl_run_confirmed": False,
        },
        "bounded_rerun_preconditions": [
            "separate_bounded_rerun_approval_packet_required",
            "observability_fields_must_be_enabled_in_runtime_trace_projection",
            "no_raw_prompt_or_argument_values_committed",
            "no_holdout_or_full_suite",
            "performance_evidence_remains_false",
        ],
        "blockers": sorted(set(blockers)),
        "observability_review_passed": review_passed,
        "next_required_action": "request_bounded_bfcl_rerun_approval_with_observability_enabled" if review_passed else "fix_observability_review_blockers_before_rerun_request",
    }


def write(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    data = build()
    if args.write:
        write(args.output, data)
    print(json.dumps(data, sort_keys=True) if args.compact else json.dumps(data, indent=2, sort_keys=True))
    return 1 if args.strict and not data["observability_review_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
