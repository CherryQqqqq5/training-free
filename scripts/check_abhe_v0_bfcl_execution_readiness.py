#!/usr/bin/env python3
"""Gate executable ABHE-v0 BFCL dev smoke readiness."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from scripts.check_abhe_v0_bfcl_dev_smoke_approval_request import check as check_request
from scripts.check_abhe_v0_bfcl_fresh_dev_slice import check as check_fresh_slice
from scripts.check_abhe_v0_bfcl_fresh_slice_review import check as check_fresh_slice_review
from scripts.check_abhe_v0_candidate_materialization_plan import check as check_candidate_plan
DEFAULT_OUTPUT=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_execution_readiness.json')
DEFAULT_APPROVAL_PACKET=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json')
REQUIRED_BLOCKERS={'bfcl_fresh_dev_slice_not_materialized','candidate_materialization_not_approved','candidate_not_materialized','dev_smoke_approval_missing','provider_model_protocol_not_approved','runtime_config_not_selected','scorer_authorization_false'}
OPTIONAL_BLOCKERS={'source_exclusion_proof_not_computed'}

def _load(path: Path)->Dict[str,Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path} must contain a JSON object')
    return data

def build_report(approval_packet: Path=DEFAULT_APPROVAL_PACKET)->Dict[str,Any]:
    fresh=check_fresh_slice(); fresh_review=check_fresh_slice_review(); cand=check_candidate_plan(); req=check_request(); b=[]; approval={}
    if not fresh.get('abhe_v0_bfcl_fresh_dev_slice_check_passed'): b += [f'fresh_slice:{x}' for x in fresh.get('blockers', [])]
    if fresh.get('fresh_dev_slice_materialized') is not True: b.append('bfcl_fresh_dev_slice_not_materialized')
    if not fresh_review.get('abhe_v0_bfcl_fresh_slice_review_passed'):
        b += [f'fresh_slice_review:{x}' for x in fresh_review.get('blockers', [])]
    if 'source_exclusion_proof_not_computed' in fresh_review.get('execution_ready_blockers', []): b.append('source_exclusion_proof_not_computed')
    if not cand.get('abhe_v0_candidate_materialization_plan_check_passed'): b += [f'candidate_plan:{x}' for x in cand.get('blockers', [])]
    if cand.get('candidate_materialized') is not True: b.append('candidate_not_materialized')
    if not req.get('abhe_v0_bfcl_dev_smoke_approval_request_passed'): b += [f'approval_request:{x}' for x in req.get('blockers', [])]
    if not approval_packet.exists():
        b += ['dev_smoke_approval_missing','candidate_materialization_not_approved','provider_model_protocol_not_approved','runtime_config_not_selected','scorer_authorization_false']
    else:
        approval=_load(approval_packet)
        if approval.get('approval_status')!='approved': b.append('dev_smoke_approval_not_approved')
        if approval.get('authorized') is not True: b.append('dev_smoke_approval_not_authorized')
        if approval.get('approval_scope')!='bounded_dev_smoke_only': b.append('approval_scope_invalid')
        if approval.get('candidate_materialization_approved') is not True: b.append('candidate_materialization_not_approved')
        if not all(approval.get(k) for k in ['approved_provider','approved_model','approved_protocol']): b.append('provider_model_protocol_not_approved')
        if not approval.get('approved_runtime_config_path'): b.append('runtime_config_not_selected')
        if approval.get('scorer_authorized') is not True: b.append('scorer_authorization_false')
        for k in ['holdout_authorized','full_suite_authorized','performance_claim_authorized']:
            if approval.get(k) is not False: b.append(f'{k}_not_false')
    b=sorted(set(b)); ready=not b
    return {'report_scope':'abhe_v0_bfcl_execution_readiness','artifact_kind':'abhe_v0_bfcl_execution_readiness','schema_version':'abhe_v0_bfcl_execution_readiness_v0','abhe_v0_bfcl_execution_ready':ready,'execution_readiness_check_passed':ready or (REQUIRED_BLOCKERS.issubset(set(b)) and set(b).issubset(REQUIRED_BLOCKERS | OPTIONAL_BLOCKERS)),'approval_packet_path':str(approval_packet),'approval_packet_present':approval_packet.exists(),'fresh_dev_slice_materialized':fresh.get('fresh_dev_slice_materialized') is True,'candidate_materialized':cand.get('candidate_materialized') is True,'execution_authorized':approval.get('authorized') is True,'scorer_authorized':approval.get('scorer_authorized') is True,'performance_evidence':False,'component_summaries':{'fresh_slice':fresh,'fresh_slice_review':fresh_review,'candidate_materialization':cand,'approval_request':req},'blockers':b}

def write_report(output: Path, report: Dict[str,Any])->None:
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(report, indent=2, sort_keys=True)+'\n', encoding='utf-8')

def main(argv: Any=None)->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--approval-packet', type=Path, default=DEFAULT_APPROVAL_PACKET); ap.add_argument('--output', type=Path, default=DEFAULT_OUTPUT); ap.add_argument('--write', action='store_true'); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try:
        r=build_report(args.approval_packet)
        if args.write: write_report(args.output, r)
    except (OSError, ValueError, json.JSONDecodeError) as exc: r={'report_scope':'abhe_v0_bfcl_execution_readiness','abhe_v0_bfcl_execution_ready':False,'execution_readiness_check_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(r, sort_keys=True) if args.compact else json.dumps(r, indent=2, sort_keys=True))
    return 1 if args.strict and not r.get('execution_readiness_check_passed') else 0
if __name__=='__main__': raise SystemExit(main())
