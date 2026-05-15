#!/usr/bin/env python3
"""Plan ABHE post-dev transitions from synthetic fixtures only."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_dev_feedback import validate_feedback
from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_FIXTURE_ROOT = Path("tests/fixtures/abhe_dev_feedback")
HIGH_NON_TARGET_REGRESSION_COUNT = 3
MAX_ACCEPTABLE_COST_DELTA_PCT = 10.0
MAX_ACCEPTABLE_LATENCY_DELTA_PCT = 10.0


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _feedback_for_validation(row: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in row.items() if key != "synthetic_fixture_kind"}


def decide_transition(row: Dict[str, Any]) -> str:
    if row.get("leakage_count", 0) > 0 or row.get("boundary_violation_count", 0) > 0:
        return "rejected_boundary_failure"
    if row.get("target_bucket_reduction", 0) <= 0:
        return "demoted_no_mechanism_signal"
    if row.get("fixed_count", 0) <= row.get("regressed_count", 0):
        return "demoted_regression_not_controlled"
    if row.get("synthetic_fixture_kind") == "mixed_strata_result":
        return "split_requested"
    if row.get("non_target_regression_count", 0) >= HIGH_NON_TARGET_REGRESSION_COUNT:
        return "narrow_router_requested"
    if (
        row.get("target_bucket_reduction", 0) > 0
        and row.get("fixed_count", 0) > row.get("regressed_count", 0)
        and row.get("cost_delta_pct", 0) <= MAX_ACCEPTABLE_COST_DELTA_PCT
        and row.get("latency_delta_pct", 0) <= MAX_ACCEPTABLE_LATENCY_DELTA_PCT
    ):
        return "dev_passed"
    return "split_requested"


def build_plan(fixture_root: Path = DEFAULT_FIXTURE_ROOT, synthetic_fixture_only: bool = False) -> Dict[str, Any]:
    if not synthetic_fixture_only:
        return {
            "report_scope": "abhe_post_dev_update_plan",
            "artifact_kind": "abhe_post_dev_update_plan",
            "post_dev_transition_planner_enabled": False,
            "does_not_read_real_feedback": True,
            "does_not_update_archive": True,
            "blockers": ["synthetic_fixture_only_required"],
        }
    blockers: List[str] = []
    transitions = []
    for path in sorted(fixture_root.glob("*.json")):
        row = _load(path)
        validation_blockers = validate_feedback(_feedback_for_validation(row), path.name)
        if validation_blockers:
            blockers.extend("fixture_%s:%s" % (path.name, blocker) for blocker in validation_blockers)
            continue
        transition = {
            "fixture_path": str(path),
            "entry_id": row.get("entry_id"),
            "from_status": "dev_smoke_executed",
            "to_status": decide_transition(row),
            "does_not_update_archive": True,
            "synthetic_fixture_only": True,
        }
        transition_blockers = scan_value(transition, label="post_dev_transition")
        blockers.extend(transition_blockers)
        transitions.append(transition)
    return {
        "report_scope": "abhe_post_dev_update_plan",
        "artifact_kind": "abhe_post_dev_update_plan",
        "schema_version": "abhe_post_dev_update_plan_v0",
        "synthetic_fixture_only": True,
        "does_not_read_real_feedback": True,
        "does_not_update_archive": True,
        "post_dev_transition_planner_enabled": False,
        "transition_count": len(transitions),
        "planned_transitions": transitions,
        "blockers": sorted(set(blockers)),
        "abhe_post_dev_update_plan_passed": not blockers,
    }


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, default=DEFAULT_FIXTURE_ROOT)
    parser.add_argument("--synthetic-fixture-only", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        plan = build_plan(args.fixture_root, args.synthetic_fixture_only)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        plan = {
            "report_scope": "abhe_post_dev_update_plan",
            "abhe_post_dev_update_plan_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(plan, sort_keys=True) if args.compact else json.dumps(plan, indent=2, sort_keys=True))
    if args.strict and not plan.get("abhe_post_dev_update_plan_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
