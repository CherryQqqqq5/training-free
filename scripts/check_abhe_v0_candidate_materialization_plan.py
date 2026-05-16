#!/usr/bin/env python3
"""Check ABHE-v0 candidate materialization remains plan-only before approval."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from scripts.build_abhe_v0_candidate_materialization_plan import DEFAULT_OUTPUT
from scripts.check_abhe_no_leakage_boundary import scan_value
FORBIDDEN_ARTIFACTS=[Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_rules.yaml'),Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_rules.yml'),Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_rules.jsonl'),Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_rule.json')]

def _load(path: Path)->Dict[str,Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path} must contain a JSON object')
    return data

def validate_plan(plan: Dict[str,Any])->List[str]:
    b=[]
    if plan.get('artifact_kind')!='abhe_v0_candidate_materialization_plan': b.append('artifact_kind_invalid')
    for k in ['approval_required','candidate_spec_approval_required','execution_approval_required']:
        if plan.get(k) is not True: b.append(f'{k}_not_true')
    for k in ['candidate_rule_generated','candidate_yaml_generated','candidate_jsonl_generated','candidate_materialized','candidate_generation_authorized','performance_evidence']:
        if plan.get(k) is not False: b.append(f'{k}_not_false')
    plans={r.get('entry_id'):r for r in plan.get('candidate_plans', [])}
    if set(plans)!={'state_tracking_v0','hallucination_abstain_v0'}: b.append('candidate_plan_entries_invalid')
    for k in ['multi_turn_only','state_carryover_evidence_required','single_turn_excluded','search_memory_watch_excluded','no_mutation']:
        if plans.get('state_tracking_v0',{}).get('boundary',{}).get(k) is not True: b.append(f'state_tracking_boundary_missing:{k}')
    for k in ['answerability_failure_only','valid_actionable_tool_use_case_excluded','false_abstain_tracked','must_not_suppress_valid_tool_calls']:
        if plans.get('hallucination_abstain_v0',{}).get('boundary',{}).get(k) is not True: b.append(f'hallucination_boundary_missing:{k}')
    for p in FORBIDDEN_ARTIFACTS:
        if p.exists(): b.append(f'unapproved_candidate_artifact_present:{p}')
    b.extend(scan_value(plan, label='abhe_v0_candidate_materialization_plan'))
    return sorted(set(b))

def check(path: Path=DEFAULT_OUTPUT)->Dict[str,Any]:
    if not path.exists(): return {'report_scope':'abhe_v0_candidate_materialization_plan_check','plan_path':str(path),'plan_present':False,'abhe_v0_candidate_materialization_plan_check_passed':False,'blockers':['candidate_materialization_plan_missing']}
    plan=_load(path); b=validate_plan(plan)
    return {'report_scope':'abhe_v0_candidate_materialization_plan_check','plan_path':str(path),'plan_present':True,'candidate_materialized':plan.get('candidate_materialized') is True,'candidate_rule_generated':plan.get('candidate_rule_generated') is True,'candidate_yaml_generated':plan.get('candidate_yaml_generated') is True,'candidate_jsonl_generated':plan.get('candidate_jsonl_generated') is True,'abhe_v0_candidate_materialization_plan_check_passed':not b,'blockers':b}

def main(argv: Any=None)->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--plan', type=Path, default=DEFAULT_OUTPUT); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try: s=check(args.plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc: s={'report_scope':'abhe_v0_candidate_materialization_plan_check','abhe_v0_candidate_materialization_plan_check_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(s, sort_keys=True) if args.compact else json.dumps(s, indent=2, sort_keys=True))
    return 1 if args.strict and not s.get('abhe_v0_candidate_materialization_plan_check_passed') else 0
if __name__=='__main__': raise SystemExit(main())
