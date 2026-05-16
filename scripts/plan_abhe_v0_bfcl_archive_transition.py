#!/usr/bin/env python3
"""Plan ABHE-v0 archive transitions from compact BFCL dev feedback without updating archive."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict
from scripts.check_abhe_no_leakage_boundary import scan_value
from scripts.check_abhe_v0_bfcl_dev_feedback import validate_feedback
DEFAULT_FEEDBACK=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.json')
DEFAULT_OUTPUT=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_archive_transition_plan.json')

def decide_transition(row: Dict[str,Any])->str:
    if row.get('leakage_count',0)>0 or row.get('boundary_violation_count',0)>0: return 'rejected_boundary_failure'
    if row.get('target_bucket_reduction',0)<=0: return 'demoted_no_mechanism_signal'
    if row.get('fixed_count',0)<=row.get('regressed_count',0): return 'demoted_regression_not_controlled'
    if row.get('non_target_regression_count',0)>=3 or row.get('false_abstain_count',0)>=3: return 'narrow_router_requested'
    if row.get('target_bucket_reduction',0)>0 and row.get('fixed_count',0)>row.get('regressed_count',0): return 'dev_passed'
    return 'split_requested'

def synthetic_feedback()->Dict[str,Any]:
    base={'case_list_hash':'synthetic_fixture_hash_not_real_validation','baseline_accuracy':0.0,'candidate_accuracy':0.0,'target_bucket_reduction':2,'fixed_count':3,'regressed_count':1,'net_fixed':2,'non_target_regression_count':0,'false_abstain_count':0,'valid_tool_call_suppression_count':0,'activation_precision':0.8,'activation_recall':0.7,'cost_delta_pct':0.0,'latency_delta_pct':0.0,'leakage_count':0,'boundary_violation_count':0,'provider_model_protocol_match':True,'fresh_slice_hash_match':True,'candidate_approved':True,'raw_material_absent':True,'holdout_touched':False,'full_suite_touched':False,'performance_claim_authorized':False}
    rows=[]
    for entry_id in ['state_tracking_v0','hallucination_abstain_v0']:
        row=dict(base); row['entry_id']=entry_id; rows.append(row)
    return {'artifact_kind':'abhe_v0_bfcl_dev_feedback','schema_version':'abhe_v0_bfcl_dev_feedback_v0','bounded_dev_smoke_only':True,'performance_evidence':False,'feedback_rows':rows}

def _load(path: Path)->Dict[str,Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path} must contain a JSON object')
    return data

def build_plan(feedback: Dict[str,Any], *, synthetic_fixture_only: bool)->Dict[str,Any]:
    blockers=validate_feedback(feedback); transitions=[]
    for row in feedback.get('feedback_rows', []): transitions.append({'entry_id':row.get('entry_id'),'from_status':'proposal_ready','to_status':decide_transition(row),'archive_updated':False,'does_not_update_archive':True,'source':'synthetic_fixture' if synthetic_fixture_only else 'compact_bfcl_dev_feedback'})
    plan={'artifact_kind':'abhe_v0_bfcl_archive_transition_plan','schema_version':'abhe_v0_bfcl_archive_transition_plan_v0','synthetic_fixture_only':synthetic_fixture_only,'archive_updated':False,'does_not_update_archive':True,'performance_evidence':False,'holdout_touched':False,'full_suite_touched':False,'planned_transitions':transitions,'next_required_action':'review_compact_dev_feedback_before_any_archive_write','blockers':sorted(set(blockers))}
    plan['blockers']=sorted(set(plan['blockers']+scan_value(plan, label='abhe_v0_bfcl_archive_transition_plan'))); plan['abhe_v0_bfcl_archive_transition_plan_passed']=not plan['blockers']; return plan

def write_plan(output: Path, plan: Dict[str,Any])->None:
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(plan, indent=2, sort_keys=True)+'\n', encoding='utf-8')

def main(argv: Any=None)->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--feedback', type=Path, default=DEFAULT_FEEDBACK); ap.add_argument('--output', type=Path, default=DEFAULT_OUTPUT); ap.add_argument('--synthetic-fixture-only', action='store_true'); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try:
        feedback=synthetic_feedback() if args.synthetic_fixture_only else _load(args.feedback); plan=build_plan(feedback, synthetic_fixture_only=args.synthetic_fixture_only); write_plan(args.output, plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc: plan={'report_scope':'abhe_v0_bfcl_archive_transition_plan','abhe_v0_bfcl_archive_transition_plan_passed':False,'blockers':[f'load_failed:{exc}'],'archive_updated':False,'does_not_update_archive':True}
    print(json.dumps(plan, sort_keys=True) if args.compact else json.dumps(plan, indent=2, sort_keys=True))
    return 1 if args.strict and not plan.get('abhe_v0_bfcl_archive_transition_plan_passed') else 0
if __name__=='__main__': raise SystemExit(main())
