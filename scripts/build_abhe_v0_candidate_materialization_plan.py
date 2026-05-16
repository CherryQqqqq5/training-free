#!/usr/bin/env python3
"""Build the ABHE-v0 candidate materialization plan without generating executable rules."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict
from scripts.check_abhe_no_leakage_boundary import scan_value
DEFAULT_OUTPUT=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_plan.json')

def build_plan() -> Dict[str, Any]:
    plan={'artifact_kind':'abhe_v0_candidate_materialization_plan','schema_version':'abhe_v0_candidate_materialization_plan_v0','approval_required':True,'candidate_spec_approval_required':True,'execution_approval_required':True,'candidate_rule_generated':False,'candidate_yaml_generated':False,'candidate_jsonl_generated':False,'candidate_materialized':False,'candidate_generation_authorized':False,'performance_evidence':False,'materialization_status':'plan_only_not_materialized','candidate_plans':[{'entry_id':'state_tracking_v0','candidate_type':'state_summary_injection','patch_mode':'runtime_prompt_or_context_injection_or_config_only_guidance','target_behavior_cluster':'multi_turn_state_lost','boundary':{'multi_turn_only':True,'state_carryover_evidence_required':True,'single_turn_excluded':True,'search_memory_watch_excluded':True,'no_mutation':True},'materialized':False},{'entry_id':'hallucination_abstain_v0','candidate_type':'evidence_boundary_verifier','patch_mode':'verifier_or_evidence_boundary_guidance','target_behavior_cluster':'unsupported_or_irrelevant_answer','boundary':{'answerability_failure_only':True,'valid_actionable_tool_use_case_excluded':True,'false_abstain_tracked':True,'must_not_suppress_valid_tool_calls':True},'materialized':False}], 'forbidden_without_approval':['candidate_rule','candidate_yaml','candidate_jsonl','candidate_pool','provider_call','bfcl_generate','bfcl_evaluate','scorer'], 'next_required_action':'request_candidate_spec_and_execution_approval_before_materialization'}
    plan['blockers']=scan_value(plan, label='abhe_v0_candidate_materialization_plan'); plan['abhe_v0_candidate_materialization_plan_passed']=not plan['blockers']; return plan

def write_plan(output: Path, plan: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(plan, indent=2, sort_keys=True)+'\n', encoding='utf-8')

def main(argv: Any=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--output', type=Path, default=DEFAULT_OUTPUT); ap.add_argument('--write', action='store_true'); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try:
        plan=build_plan();
        if args.write: write_plan(args.output, plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc: plan={'report_scope':'abhe_v0_candidate_materialization_plan','abhe_v0_candidate_materialization_plan_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(plan, sort_keys=True) if args.compact else json.dumps(plan, indent=2, sort_keys=True))
    return 1 if args.strict and not plan.get('abhe_v0_candidate_materialization_plan_passed') else 0
if __name__=='__main__': raise SystemExit(main())
