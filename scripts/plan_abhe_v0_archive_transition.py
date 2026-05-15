#!/usr/bin/env python3
"""Plan ABHE-v0 archive transitions from synthetic feedback without updating archive."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.plan_abhe_post_dev_update import decide_transition

DEFAULT_FEEDBACK = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_synthetic_dev_feedback.json")
DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_archive_transition_plan.json")


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def build_plan(feedback_path: Path = DEFAULT_FEEDBACK) -> Dict[str, Any]:
    feedback = _load(feedback_path)
    blockers: List[str] = []
    for key in ["synthetic_fixture_only", "does_not_call_provider", "does_not_call_bfcl_or_model", "does_not_authorize_scorer"]:
        if feedback.get(key) is not True:
            blockers.append("feedback_%s_not_true" % key)
    for key in ["paired_dev_smoke_executed", "fresh_dev_slice_materialized", "candidate_rule_generated", "candidate_yaml_generated", "candidate_jsonl_generated", "performance_evidence"]:
        if feedback.get(key) is not False:
            blockers.append("feedback_%s_not_false" % key)
    transitions = []
    for row in feedback.get("feedback_rows", []):
        transitions.append({
            "entry_id": row.get("entry_id"),
            "from_status": "proposal_ready",
            "to_status": decide_transition(row),
            "synthetic_fixture_only": True,
            "does_not_update_archive": True,
            "paired_dev_smoke_executed": False,
            "performance_evidence": False,
        })
    if {row["entry_id"] for row in transitions} != {"state_tracking_v0", "hallucination_abstain_v0"}:
        blockers.append("transition_plan_expected_two_entries_missing")
    artifact = {
        "artifact_kind": "abhe_v0_archive_transition_plan",
        "schema_version": "abhe_v0_archive_transition_plan_v0",
        "synthetic_fixture_only": True,
        "does_not_update_archive": True,
        "archive_updated": False,
        "paired_dev_smoke_executed": False,
        "performance_evidence": False,
        "planned_transitions": transitions,
        "next_required_action": "request_minimal_real_trace_or_fresh_dev_slice_approval_before_live_dev_smoke",
        "blockers": sorted(set(blockers)),
    }
    artifact["blockers"] = sorted(set(artifact["blockers"] + scan_value(artifact, label="abhe_v0_archive_transition_plan")))
    artifact["abhe_v0_archive_transition_plan_passed"] = not artifact["blockers"]
    return artifact


def write_plan(output: Path, artifact: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        artifact = build_plan(args.feedback)
        if args.write:
            write_plan(args.output, artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        artifact = {
            "report_scope": "abhe_v0_archive_transition_plan",
            "abhe_v0_archive_transition_plan_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(artifact, sort_keys=True) if args.compact else json.dumps(artifact, indent=2, sort_keys=True))
    if args.strict and not artifact.get("abhe_v0_archive_transition_plan_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
