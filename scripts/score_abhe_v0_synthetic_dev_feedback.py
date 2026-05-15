#!/usr/bin/env python3
"""Create ABHE-v0 synthetic dev feedback for the selected non-executable specs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_CANDIDATES = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_simple_candidate_specs.json")
DEFAULT_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_synthetic_dev_feedback.json")


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def build_feedback(candidate_path: Path = DEFAULT_CANDIDATES) -> Dict[str, Any]:
    candidates = _load(candidate_path)
    blockers: List[str] = []
    if candidates.get("candidate_rule_generated") is not False:
        blockers.append("candidate_rule_generated_not_false")
    if candidates.get("candidate_yaml_generated") is not False:
        blockers.append("candidate_yaml_generated_not_false")
    if candidates.get("candidate_jsonl_generated") is not False:
        blockers.append("candidate_jsonl_generated_not_false")
    if candidates.get("performance_evidence") is not False:
        blockers.append("candidate_specs_performance_evidence_not_false")
    rows = []
    for spec in candidates.get("specs", []):
        entry_id = spec.get("entry_id")
        if entry_id == "state_tracking_v0":
            rows.append({
                "entry_id": entry_id,
                "synthetic_fixture_only": True,
                "paired_dev_smoke_executed": False,
                "fresh_dev_slice_materialized": False,
                "target_bucket_reduction": 3,
                "fixed_count": 4,
                "regressed_count": 1,
                "net_fixed": 3,
                "non_target_regression_count": 1,
                "activation_precision": 0.8,
                "activation_recall": 0.7,
                "cost_delta_pct": 2.0,
                "latency_delta_pct": 3.0,
                "leakage_count": 0,
                "boundary_violation_count": 0,
                "performance_evidence": False,
            })
        elif entry_id == "hallucination_abstain_v0":
            rows.append({
                "entry_id": entry_id,
                "synthetic_fixture_only": True,
                "paired_dev_smoke_executed": False,
                "fresh_dev_slice_materialized": False,
                "target_bucket_reduction": 2,
                "fixed_count": 3,
                "regressed_count": 0,
                "net_fixed": 3,
                "non_target_regression_count": 1,
                "activation_precision": 0.75,
                "activation_recall": 0.65,
                "cost_delta_pct": 1.0,
                "latency_delta_pct": 2.0,
                "leakage_count": 0,
                "boundary_violation_count": 0,
                "false_abstain_count": 1,
                "performance_evidence": False,
            })
    if {row["entry_id"] for row in rows} != {"state_tracking_v0", "hallucination_abstain_v0"}:
        blockers.append("synthetic_feedback_expected_two_entries_missing")
    artifact = {
        "artifact_kind": "abhe_v0_synthetic_dev_feedback",
        "schema_version": "abhe_v0_synthetic_dev_feedback_v0",
        "synthetic_fixture_only": True,
        "paired_dev_smoke_executed": False,
        "does_not_call_provider": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "fresh_dev_slice_materialized": False,
        "candidate_rule_generated": False,
        "candidate_yaml_generated": False,
        "candidate_jsonl_generated": False,
        "performance_evidence": False,
        "feedback_rows": rows,
        "blockers": sorted(set(blockers)),
    }
    artifact["blockers"] = sorted(set(artifact["blockers"] + scan_value(artifact, label="abhe_v0_synthetic_dev_feedback")))
    artifact["abhe_v0_synthetic_dev_feedback_passed"] = not artifact["blockers"]
    return artifact


def write_feedback(output: Path, artifact: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-specs", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        artifact = build_feedback(args.candidate_specs)
        if args.write:
            write_feedback(args.output, artifact)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        artifact = {
            "report_scope": "abhe_v0_synthetic_dev_feedback",
            "abhe_v0_synthetic_dev_feedback_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(artifact, sort_keys=True) if args.compact else json.dumps(artifact, indent=2, sort_keys=True))
    if args.strict and not artifact.get("abhe_v0_synthetic_dev_feedback_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
