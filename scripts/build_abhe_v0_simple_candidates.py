#!/usr/bin/env python3
"""Build ABHE-v0 synthetic policy scores and non-executable candidate specs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_TAXONOMY = Path("abhe_archive/behavior_taxonomy_v0.json")
DEFAULT_SCORE_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_policy_score.json")
DEFAULT_CANDIDATE_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_simple_candidate_specs.json")
DEFAULT_SLICE_OUTPUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_synthetic_fresh_dev_slice_manifest.json")
SCORE_FIELDS = ["fixability_prior", "mechanism_clarity", "safety_prior", "readiness", "overfit_guard"]


def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("%s must contain a JSON object" % path)
    return data


def _score(entry: Dict[str, Any]) -> float:
    return round(sum(float(entry[field]) for field in SCORE_FIELDS) / len(SCORE_FIELDS), 4)


def validate_taxonomy(taxonomy: Dict[str, Any]) -> List[str]:
    blockers = []
    entries = taxonomy.get("entries")
    if taxonomy.get("artifact_kind") != "abhe_behavior_taxonomy":
        blockers.append("taxonomy_artifact_kind_invalid")
    if taxonomy.get("performance_evidence") is not False:
        blockers.append("taxonomy_performance_evidence_not_false")
    for key in ("does_not_call_provider", "does_not_call_bfcl_or_model", "does_not_authorize_scorer", "does_not_generate_candidate_rule"):
        if taxonomy.get(key) is not True:
            blockers.append("taxonomy_%s_not_true" % key)
    if not isinstance(entries, list) or len(entries) < 8 or len(entries) > 10:
        blockers.append("taxonomy_entry_count_outside_v0_range")
        return blockers
    seen = set()
    for entry in entries:
        entry_id = entry.get("entry_id")
        if entry_id in seen:
            blockers.append("taxonomy_duplicate_entry_id:%s" % entry_id)
        seen.add(entry_id)
        for key in ["entry_id", "level_1_family", "level_2_cluster", "status", "summary", "recommended_candidate_type"]:
            if not entry.get(key):
                blockers.append("taxonomy_%s_missing:%s" % (key, entry_id))
        for field in SCORE_FIELDS:
            value = entry.get(field)
            if not isinstance(value, (int, float)) or value < 0 or value > 1:
                blockers.append("taxonomy_score_field_invalid:%s:%s" % (entry_id, field))
    blockers.extend(scan_value(taxonomy, label="abhe_v0_taxonomy"))
    return sorted(set(blockers))


def build_outputs(taxonomy_path: Path = DEFAULT_TAXONOMY) -> Dict[str, Any]:
    taxonomy = _load(taxonomy_path)
    blockers = validate_taxonomy(taxonomy)
    scored = []
    for entry in taxonomy.get("entries", []):
        scored.append({
            "entry_id": entry["entry_id"],
            "status": entry["status"],
            "level_1_family": entry["level_1_family"],
            "level_2_cluster": entry["level_2_cluster"],
            "score": _score(entry),
            "score_components": {field: entry[field] for field in SCORE_FIELDS},
            "recommended_candidate_type": entry["recommended_candidate_type"],
        })
    scored.sort(key=lambda row: (-row["score"], row["entry_id"]))
    selected = [row for row in scored if row["status"] == "proposal_ready"][:2]
    if [row["entry_id"] for row in selected] != ["state_tracking_v0", "hallucination_abstain_v0"]:
        blockers.append("unexpected_top2_selection:%s" % ",".join(row["entry_id"] for row in selected))

    policy_score = {
        "artifact_kind": "abhe_v0_policy_score",
        "schema_version": "abhe_v0_policy_score_v0",
        "synthetic_dry_run_only": True,
        "does_not_call_provider": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "performance_evidence": False,
        "score_formula": "mean(fixability_prior, mechanism_clarity, safety_prior, readiness, overfit_guard)",
        "scored_entries": scored,
        "selected_entry_ids": [row["entry_id"] for row in selected],
        "watch_entry_ids": [row["entry_id"] for row in scored if row["status"] == "watch"],
        "candidate_pool_next_entry_ids": [row["entry_id"] for row in scored if row["status"] == "candidate_pool_next"],
        "blockers": blockers,
        "abhe_v0_policy_score_passed": not blockers,
    }
    candidate_specs = {
        "artifact_kind": "abhe_v0_simple_candidate_specs",
        "schema_version": "abhe_v0_simple_candidate_specs_v0",
        "synthetic_dry_run_only": True,
        "candidate_rule_generated": False,
        "candidate_yaml_generated": False,
        "candidate_jsonl_generated": False,
        "candidate_pool_ready": False,
        "candidate_generation_authorized": False,
        "performance_evidence": False,
        "specs": [
            {
                "entry_id": "state_tracking_v0",
                "candidate_type": "state_summary_injection",
                "target_behavior_cluster": "multi_turn_state_lost",
                "activation_boundary": "multi_turn_only_state_carryover_evidence_required",
                "non_target_exclusions": ["single_turn", "search_memory_watch", "state_mutation"],
                "primary_metrics": ["target_bucket_reduction", "fixed_count", "regressed_count"],
                "safety_metrics": ["non_target_regression_count", "latency_delta_pct", "cost_delta_pct"],
                "materialized": False,
            },
            {
                "entry_id": "hallucination_abstain_v0",
                "candidate_type": "evidence_boundary_verifier",
                "target_behavior_cluster": "unsupported_or_irrelevant_answer",
                "activation_boundary": "answerability_failure_only",
                "non_target_exclusions": ["valid_actionable_tool_use", "sufficient_evidence_cases"],
                "primary_metrics": ["target_bucket_reduction", "false_abstain_count", "fixed_count", "regressed_count"],
                "safety_metrics": ["valid_tool_call_suppression_count", "non_target_regression_count"],
                "materialized": False,
            },
        ],
        "blockers": scan_value({"selected_entry_ids": [row["entry_id"] for row in selected]}, label="abhe_v0_candidate_specs"),
        "abhe_v0_candidate_specs_passed": not blockers,
    }
    slice_manifest = {
        "artifact_kind": "abhe_v0_synthetic_fresh_dev_slice_manifest",
        "schema_version": "abhe_v0_synthetic_fresh_dev_slice_manifest_v0",
        "synthetic_dry_run_only": True,
        "fresh_dev_slice_materialized": False,
        "source_160_compact_cases_reused_for_validation": False,
        "archive_seed_source_excluded": True,
        "selected_case_ids_hash": "pending_no_real_case_ids_materialized",
        "entry_case_caps": {
            "state_tracking_v0": "10_to_20_future_fresh_cases",
            "hallucination_abstain_v0": "10_to_20_future_fresh_cases"
        },
        "performance_evidence": False,
    }
    return {
        "policy_score": policy_score,
        "candidate_specs": candidate_specs,
        "slice_manifest": slice_manifest,
    }


def write_outputs(outputs: Dict[str, Any], score_output: Path, candidate_output: Path, slice_output: Path) -> None:
    for path, data in [
        (score_output, outputs["policy_score"]),
        (candidate_output, outputs["candidate_specs"]),
        (slice_output, outputs["slice_manifest"]),
    ]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    parser.add_argument("--score-output", type=Path, default=DEFAULT_SCORE_OUTPUT)
    parser.add_argument("--candidate-output", type=Path, default=DEFAULT_CANDIDATE_OUTPUT)
    parser.add_argument("--slice-output", type=Path, default=DEFAULT_SLICE_OUTPUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        outputs = build_outputs(args.taxonomy)
        if args.write:
            write_outputs(outputs, args.score_output, args.candidate_output, args.slice_output)
        summary = {
            "report_scope": "abhe_v0_simple_candidate_builder",
            "abhe_v0_simple_candidate_builder_passed": outputs["policy_score"]["abhe_v0_policy_score_passed"],
            "selected_entry_ids": outputs["policy_score"]["selected_entry_ids"],
            "candidate_rule_generated": False,
            "candidate_yaml_generated": False,
            "candidate_jsonl_generated": False,
            "fresh_dev_slice_materialized": False,
            "performance_evidence": False,
            "blockers": outputs["policy_score"]["blockers"],
        }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "abhe_v0_simple_candidate_builder",
            "abhe_v0_simple_candidate_builder_passed": False,
            "blockers": ["load_failed:%s" % exc],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary.get("abhe_v0_simple_candidate_builder_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
