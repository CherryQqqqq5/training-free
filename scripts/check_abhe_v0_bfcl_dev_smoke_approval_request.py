#!/usr/bin/env python3
"""Check the ABHE-v0 BFCL dev smoke approval request without approving execution."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from scripts.check_abhe_no_leakage_boundary import scan_value
DEFAULT_REQUEST=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_request.json')
FORCED_FALSE=['authorized','execution_started','provider_calls_authorized','bfcl_generate_authorized','bfcl_evaluate_authorized','scorer_authorized','performance_evidence','holdout_authorized','full_suite_authorized','sota_3pp_claim_ready','huawei_acceptance_ready']

def validate_request(r: Dict[str,Any])->List[str]:
    b=[]
    if r.get('artifact_kind')!='abhe_v0_bfcl_dev_smoke_approval_request': b.append('artifact_kind_invalid')
    if r.get('approval_status')!='pending': b.append('approval_status_not_pending')
    if r.get('scope')!='bounded_dev_smoke_only': b.append('scope_invalid')
    for k in FORCED_FALSE:
        if r.get(k) is not False: b.append(f'{k}_not_false')
    if r.get('artifact_boundary')!='compact_only': b.append('artifact_boundary_not_compact_only')
    required={'raw_leakage','provider_model_protocol_mismatch','case_list_hash_mismatch','candidate_rule_unapproved','fresh_slice_not_materialized','cost_latency_cap_exceeded','regression_cap_exceeded','scorer_artifact_schema_failure'}
    if not required.issubset(set(r.get('stop_loss', []))): b.append('stop_loss_incomplete')
    b.extend(scan_value(r, label='abhe_v0_bfcl_dev_smoke_approval_request'))
    return sorted(set(b))

def build_request()->Dict[str,Any]:
    r={'artifact_kind':'abhe_v0_bfcl_dev_smoke_approval_request','schema_version':'abhe_v0_bfcl_dev_smoke_approval_request_v0','approval_status':'pending','authorized':False,'execution_started':False,'scope':'bounded_dev_smoke_only','provider_calls_authorized':False,'bfcl_generate_authorized':False,'bfcl_evaluate_authorized':False,'scorer_authorized':False,'performance_evidence':False,'holdout_authorized':False,'full_suite_authorized':False,'sota_3pp_claim_ready':False,'huawei_acceptance_ready':False,'entry_ids':['state_tracking_v0','hallucination_abstain_v0'],'baseline_arm_command_template':'PYTHONPATH=.:src .venv/bin/python scripts/run_abhe_v0_bfcl_dev_smoke.py --execute-approved --approval-packet outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json --arm baseline --compact-only','candidate_arm_command_template':'PYTHONPATH=.:src .venv/bin/python scripts/run_abhe_v0_bfcl_dev_smoke.py --execute-approved --approval-packet outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json --arm candidate --compact-only','selected_case_list_hash':'pending_until_fresh_slice_materialized','provider_model_protocol':'pending_approval','runtime_config_path':'pending_approval','candidate_materialization_plan_path':'outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_plan.json','artifact_boundary':'compact_only','stop_loss':['raw_leakage','provider_model_protocol_mismatch','case_list_hash_mismatch','candidate_rule_unapproved','fresh_slice_not_materialized','cost_latency_cap_exceeded','regression_cap_exceeded','scorer_artifact_schema_failure'],'next_required_action':'request_explicit_abhe_v0_bfcl_dev_smoke_approval_packet'}
    r['blockers']=validate_request(r); r['abhe_v0_bfcl_dev_smoke_approval_request_passed']=not r['blockers']; return r

def _load(path: Path)->Dict[str,Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path} must contain a JSON object')
    return data

def write_request(path: Path, r: Dict[str,Any])->None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(r, indent=2, sort_keys=True)+'\n', encoding='utf-8')

def check(path: Path=DEFAULT_REQUEST)->Dict[str,Any]:
    if not path.exists(): return {'report_scope':'abhe_v0_bfcl_dev_smoke_approval_request_check','request_path':str(path),'request_present':False,'abhe_v0_bfcl_dev_smoke_approval_request_passed':False,'blockers':['dev_smoke_approval_request_missing']}
    r=_load(path); b=validate_request(r)
    return {'report_scope':'abhe_v0_bfcl_dev_smoke_approval_request_check','request_path':str(path),'request_present':True,'approval_status':r.get('approval_status'),'authorized':r.get('authorized'),'performance_evidence':r.get('performance_evidence'),'abhe_v0_bfcl_dev_smoke_approval_request_passed':not b,'blockers':b}

def main(argv: Any=None)->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--request', type=Path, default=DEFAULT_REQUEST); ap.add_argument('--write-default', action='store_true'); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try:
        if args.write_default: write_request(args.request, build_request())
        s=check(args.request)
    except (OSError, ValueError, json.JSONDecodeError) as exc: s={'report_scope':'abhe_v0_bfcl_dev_smoke_approval_request_check','abhe_v0_bfcl_dev_smoke_approval_request_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(s, sort_keys=True) if args.compact else json.dumps(s, indent=2, sort_keys=True))
    return 1 if args.strict and not s.get('abhe_v0_bfcl_dev_smoke_approval_request_passed') else 0
if __name__=='__main__': raise SystemExit(main())
