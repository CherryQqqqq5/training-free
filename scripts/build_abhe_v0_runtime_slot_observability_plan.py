#!/usr/bin/env python3
"""Build a fail-closed observability plan before any ABHE runtime-slot BFCL rerun."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

OUT = Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_observability_plan.json")

SAFE_LABELS = [
    "pre_generation_required_arg_ledger_available",
    "pre_generation_tool_schema_keyset_hash",
    "pre_generation_intended_tool_known",
    "pre_generation_request_patch_set_hash",
    "pre_generation_adapter_projection_hash",
    "post_decode_tool_call_present",
    "post_decode_tool_name_hash",
    "post_decode_argument_keyset_hash",
    "post_decode_missing_required_arg_count_before_repair",
    "post_decode_provider_generated_valid_call_proxy",
    "post_decode_no_tool_call_final_response",
    "post_response_existing_validator_repair_kind_counts",
    "post_response_runtime_slot_policy_hit",
    "post_response_runtime_slot_bind_repair_count",
    "post_response_controller_not_applicable_reason",
    "post_response_argument_keyset_changed_by_repair",
]

FORBIDDEN_SURFACES = [
    "raw_prompt_literal",
    "raw_tool_argument_value",
    "raw_tool_schema_body",
    "raw_provider_payload",
    "raw_bfcl_result_tree",
    "gold_expected_reference_answer",
    "scorer_diff",
    "candidate_output_text",
    "api_key_or_endpoint_value",
]

ANCHORS = [
    {
        "surface": "pre_generation_request_context",
        "file": "src/grc/runtime/proxy.py",
        "purpose": "record compact hashes for adapter projection and request patch markers before provider call",
    },
    {
        "surface": "post_decode_tool_call_structure",
        "file": "src/grc/runtime/engine.py",
        "purpose": "record tool-call presence, tool-name hash, argument keyset hash, and missing required arg count before repairs",
    },
    {
        "surface": "runtime_slot_controller_attribution",
        "file": "src/grc/runtime/slot_controller.py",
        "purpose": "separate actual bind repairs, not-applicable reasons, and existing-validator repairs",
    },
    {
        "surface": "trace_capture_compact_projection",
        "file": "scripts/audit_abhe_v0_runtime_slot_controller_bindability.py",
        "purpose": "consume only compact trace fields and reject raw material before any BFCL rerun interpretation",
    },
]


def build() -> Dict[str, Any]:
    return {
        "artifact_kind": "abhe_v0_runtime_slot_observability_plan",
        "schema_version": "abhe_v0_runtime_slot_observability_plan_v0",
        "plan_status": "review_plan_only",
        "approval_status": "not_requested",
        "authorized": False,
        "implementation_started": False,
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
        "goal": "disambiguate provider_guidance_vs_existing_validator_repair_vs_runtime_slot_bind_before_any_bfcl_rerun",
        "causality_gap_addressed": "runtime_slot_controller_v2_score_gain_real_but_direct_bind_causality_unconfirmed",
        "source_evidence": {
            "bindability_audit": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_bindability_audit_v1.json",
            "path_replay": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_path_replay.json",
            "causality_audit": "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_causality_audit.json",
        },
        "instrumentation_anchors": ANCHORS,
        "safe_compact_labels": SAFE_LABELS,
        "forbidden_surfaces": FORBIDDEN_SURFACES,
        "future_trace_row_contract": {
            "case_stable_hash": "sha256_only",
            "arm": "enum_only",
            "bfcl_category": "enum_only",
            "pre_generation": [label for label in SAFE_LABELS if label.startswith("pre_generation_")],
            "post_decode": [label for label in SAFE_LABELS if label.startswith("post_decode_")],
            "post_response": [label for label in SAFE_LABELS if label.startswith("post_response_")],
            "raw_material_absent": True,
            "argument_values_committed": False,
            "provider_payload_committed": False,
            "scorer_diff_committed": False,
        },
        "promotion_blockers_until_implemented": [
            "pre_generation_observability_not_implemented",
            "post_decode_observability_not_implemented",
            "runtime_slot_bind_causality_not_confirmed",
            "bfcl_rerun_requires_separate_bounded_approval_after_observability_gate",
        ],
        "observability_plan_ready": True,
        "bfcl_rerun_authorized_by_this_plan": False,
        "next_required_action": "implement_pre_generation_post_decode_observability_no_provider_fixture_before_bfcl_rerun",
        "raw_material_absent": True,
        "safe_fields_only": True,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
