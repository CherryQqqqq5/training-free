#!/usr/bin/env python3
"""Build ABHE-v0 next residual child candidate specs without executable rules."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from scripts.check_abhe_no_leakage_boundary import scan_value

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
OUT = ROOT / "abhe_v0_next_candidate_specs.json"
MANIFEST = ROOT / "abhe_v0_next_fresh_slice_manifest.json"


def _load_hash() -> str:
    if not MANIFEST.exists():
        return "pending_until_next_fresh_slice_manifest"
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return str(data.get("selected_case_ids_hash", "pending_until_next_fresh_slice_manifest"))


def build() -> Dict[str, Any]:
    selected_hash = _load_hash()
    spec = {
        "artifact_kind": "abhe_v0_next_candidate_specs",
        "schema_version": "abhe_v0_next_candidate_specs_v0",
        "bounded_dev_smoke_only": True,
        "selected_case_ids_hash": selected_hash,
        "candidate_rule_generated": False,
        "candidate_yaml_generated": False,
        "candidate_jsonl_generated": False,
        "candidate_pool_ready": False,
        "archive_update_authorized": False,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "frozen_mechanisms": [
            {
                "mechanism_id": "post_tool_continuation_guard_v0",
                "status": "frozen_protocol_invariant",
                "target_substrata": ["multi_turn_base", "multi_turn_miss_func"],
                "not_tuned_on_old_expanded_slice": True,
                "validation_role": "generalization_guard",
            },
            {
                "mechanism_id": "no_tool_boundary_v0",
                "status": "frozen_regression_suite",
                "target_substrata": ["irrelevance", "live_irrelevance", "live_relevance"],
                "not_tuned_on_old_expanded_slice": True,
                "validation_role": "false_abstain_and_valid_tool_guard",
            },
        ],
        "new_child_mechanisms": [
            {
                "mechanism_id": "missing_param_epistemic_gate_v0",
                "candidate_type": "epistemic_slot_gate_compact_guidance",
                "target_substratum": "multi_turn_miss_param",
                "mechanism_contract": [
                    "check_prior_turn_state_before_asking",
                    "check_prior_tool_observed_state_before_asking",
                    "use_available_lookup_tool_when_slot_is_recoverable",
                    "ask_or_insufficient_only_when_slot_is_unknown_and_not_recoverable",
                    "do_not_hallucinate_required_arguments",
                    "do_not_suppress_valid_tool_calls_when_required_arguments_are_available",
                ],
                "negative_controls": [
                    "slot_already_exists_in_prior_turn",
                    "slot_exists_in_prior_tool_result",
                    "slot_tool_recoverable",
                    "slot_unrecoverable",
                    "valid_tool_call_has_all_required_arguments",
                ],
                "primary_success_signal": "improves_multi_turn_miss_param_vs_frozen_v2_on_fresh_slice",
                "secondary_safety_signals": {
                    "false_ask_count": "strict_threshold",
                    "hallucinated_param_count": 0,
                    "valid_tool_call_suppression_count": 0,
                    "non_target_regression_count": 0,
                },
            },
            {
                "mechanism_id": "long_context_state_retrieval_v0",
                "candidate_type": "long_context_state_resolution_compact_guidance",
                "target_substratum": "multi_turn_long_context",
                "mechanism_contract": [
                    "read_before_write",
                    "resolve_entity_references_against_latest_user_intent_or_confirmed_selection",
                    "prefer_latest_valid_state_over_stale_state",
                    "filter_tool_results_by_active_state",
                    "do_not_guess_state_from_long_context_when_unresolved",
                ],
                "negative_controls": [
                    "two_similar_entities_only_one_active",
                    "old_state_later_overwritten",
                    "tool_result_has_irrelevant_candidates",
                    "indirect_reference_to_prior_selected_option",
                    "state_absent_must_not_guess",
                ],
                "primary_success_signal": "improves_multi_turn_long_context_vs_frozen_v2_on_fresh_slice",
                "secondary_safety_signals": {
                    "entity_misbind_count": 0,
                    "stale_state_use_count": 0,
                    "unsupported_state_guess_count": 0,
                    "non_target_regression_count": 0,
                },
            },
        ],
        "arm_definitions": {
            "baseline": [],
            "frozen_v2": ["post_tool_continuation_guard_v0", "no_tool_boundary_v0"],
            "missing_param_gate": ["post_tool_continuation_guard_v0", "no_tool_boundary_v0", "missing_param_epistemic_gate_v0"],
            "long_context_retrieval": ["post_tool_continuation_guard_v0", "no_tool_boundary_v0", "long_context_state_retrieval_v0"],
            "both": ["post_tool_continuation_guard_v0", "no_tool_boundary_v0", "missing_param_epistemic_gate_v0", "long_context_state_retrieval_v0"],
        },
        "overfit_guard_controls": {
            "prompt_literal_conditions_used": False,
            "case_identifier_hash_allowlists_used": False,
            "bfcl_category_specific_trigger_rules_used": False,
            "evaluator_target_condition_rules_used": False,
            "same_expanded_slice_tuning_used": False,
        },
        "raw_material_absent": True,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "scorer_diff_committed": False,
    }
    blockers: List[str] = scan_value(spec, label="abhe_v0_next_candidate_specs")
    spec["blockers"] = sorted(set(blockers))
    return spec


def write(data: Dict[str, Any]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    data = build()
    if args.write:
        write(data)
    print(json.dumps(data, sort_keys=True) if args.compact else json.dumps(data, indent=2, sort_keys=True))
    return 1 if args.strict and data.get("blockers") else 0


if __name__ == "__main__":
    raise SystemExit(main())
