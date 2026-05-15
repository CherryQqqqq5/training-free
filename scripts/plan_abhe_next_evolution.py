#!/usr/bin/env python3
"""Plan the next ABHE evolution requests without running models, BFCL, or scorer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_archive_policy import DEFAULT_ARCHIVE, DEFAULT_OPPORTUNITY, validate_archive
from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_next_evolution_plan.json")

FALSE_AUTH_FLAGS = {
    "provider_calls_authorized": False,
    "bfcl_generate_authorized": False,
    "bfcl_evaluate_authorized": False,
    "candidate_generation_authorized": False,
    "candidate_jsonl_authorized": False,
    "candidate_activation_authorized": False,
    "candidate_pool_ready": False,
    "scorer_authorized": False,
    "performance_evidence": False,
    "sota_3pp_claim_ready": False,
    "huawei_acceptance_ready": False,
}


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _load_feedback(root: Path) -> List[Dict[str, Any]]:
    if not root.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        data = _load(path)
        data["_feedback_path"] = str(path)
        rows.append(data)
    return rows


def build_plan(
    archive: Dict[str, Any],
    opportunity: Dict[str, Any],
    feedback_rows: List[Dict[str, Any]],
    archive_path: Path = DEFAULT_ARCHIVE,
    opportunity_path: Path = DEFAULT_OPPORTUNITY,
) -> Dict[str, Any]:
    blockers = validate_archive(archive, opportunity)
    if feedback_rows:
        blockers.append("dev_feedback_present_post_dev_planner_not_implemented")
    selected_actions = []
    watch_actions = []
    entries = archive.get("entries") if isinstance(archive.get("entries"), list) else []
    opportunity_by_id = {
        row.get("entry_id"): row
        for row in opportunity.get("entries", [])
        if isinstance(row, dict)
    }
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        row = opportunity_by_id.get(entry.get("entry_id"), {})
        item = {
            "entry_id": entry.get("entry_id"),
            "action": entry.get("recommended_action"),
            "reason": row.get("reason") or "archive_policy_selected",
            "source_evidence_count": entry.get("source_evidence_count"),
            "coverage_strata": entry.get("coverage_strata"),
            "target_behavior_cluster": entry.get("target_behavior_cluster"),
        }
        if entry.get("status") == "proposal_ready":
            selected_actions.append(item)
        elif entry.get("status") == "watch":
            watch_actions.append(item)
    plan = {
        "artifact_kind": "abhe_next_evolution_plan",
        "schema_version": "abhe_next_evolution_plan_v0",
        "source_archive": str(archive_path),
        "source_opportunity_table": str(opportunity_path),
        "source_evidence_role": "discovery_archive_seed_only",
        "does_not_call_provider": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "does_not_generate_candidate": True,
        "does_not_claim_performance": True,
        "requires_fresh_dev_slice": True,
        "trace_packet_is_separate_from_dev_smoke_packet": True,
        "selected_actions": selected_actions,
        "watch_actions": watch_actions,
        "not_selected_actions": [],
        "next_required_packets": [
            "temporary_trace_extraction_approval_packet",
            "abhe_bounded_dev_smoke_execution_packet",
        ],
        "forbidden_interpretations": [
            "160_compact_cases_as_performance_improvement",
            "bfcl_category_to_skill_mapping",
            "rashe_as_current_complete_method",
            "deterministic_argument_repair_as_active_next_step",
            "search_memory_mixed_entry_direct_to_scorer",
        ],
        "blockers": blockers,
    }
    if feedback_rows:
        plan["next_required_action"] = "run_check_abhe_dev_feedback_and_enable_post_dev_planner"
    plan.update(FALSE_AUTH_FLAGS)
    leakage_blockers = scan_value(plan, label="plan")
    plan["blockers"] = sorted(set(plan["blockers"] + leakage_blockers))
    return plan


def write_plan(output: Path, plan: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-index", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--opportunity-table", type=Path, default=DEFAULT_OPPORTUNITY)
    parser.add_argument("--dev-feedback-root", type=Path, default=Path("abhe_archive/dev_feedback"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        archive = _load(args.archive_index)
        opportunity = _load(args.opportunity_table)
        feedback_rows = _load_feedback(args.dev_feedback_root)
        plan = build_plan(archive, opportunity, feedback_rows, args.archive_index, args.opportunity_table)
        if args.write:
            write_plan(args.output, plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        plan = {"artifact_kind": "abhe_next_evolution_plan", "blockers": ["load_failed:%s" % exc]}
    print(json.dumps(plan, sort_keys=True) if args.compact else json.dumps(plan, indent=2, sort_keys=True))
    if args.strict and plan.get("blockers"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
