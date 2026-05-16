#!/usr/bin/env python3
"""Check approved ABHE-v0 minimal materialized candidates remain compact and non-executed."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_APPROVAL_PACKET=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_approval_packet.json')
DEFAULT_CANDIDATES=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_materialized_candidates.json')
DEFAULT_FRESH_MANIFEST=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_manifest.json')
EXPECTED_HASH='sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f'
EXPECTED_ENTRIES={'state_tracking_v0','hallucination_abstain_v0'}
EXPECTED_TYPES={'state_tracking_v0':'state_summary_injection','hallucination_abstain_v0':'evidence_boundary_verifier'}
FALSE_APPROVAL_KEYS=['provider_calls_authorized','bfcl_generate_authorized','bfcl_evaluate_authorized','scorer_authorized','dev_smoke_execution_authorized','candidate_jsonl_authorized','candidate_pool_authorized','performance_evidence','holdout_authorized','full_suite_authorized','sota_3pp_claim_ready','huawei_acceptance_ready']
FALSE_CANDIDATE_KEYS=['candidate_rule_generated','candidate_yaml_generated','candidate_jsonl_generated','candidate_pool_ready','execution_authorized','performance_evidence','provider_calls_authorized','bfcl_generate_authorized','bfcl_evaluate_authorized','scorer_authorized']
FORBIDDEN_ARTIFACTS=[Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_rules.yaml'),Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_rules.yml'),Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_rules.jsonl'),Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_rule.json'),Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_pool.json'),Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_pool')]

def _load(path: Path)->Dict[str,Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path} must contain a JSON object')
    return data

def validate_approval(packet: Dict[str,Any], fresh_hash: str)->List[str]:
    b=[]
    if packet.get('artifact_kind')!='abhe_v0_candidate_materialization_approval_packet': b.append('approval_artifact_kind_invalid')
    if packet.get('schema_version')!='abhe_v0_candidate_materialization_approval_packet_v0': b.append('approval_schema_version_invalid')
    if packet.get('approval_status')!='approved': b.append('approval_status_not_approved')
    if packet.get('authorized') is not True: b.append('approval_authorized_not_true')
    if packet.get('approval_scope')!='candidate_materialization_only': b.append('approval_scope_invalid')
    if set(packet.get('approved_entry_ids', []))!=EXPECTED_ENTRIES: b.append('approved_entry_ids_invalid')
    if packet.get('approved_candidate_types')!=EXPECTED_TYPES: b.append('approved_candidate_types_invalid')
    if packet.get('approved_fresh_dev_slice_hash')!=fresh_hash: b.append('approved_fresh_dev_slice_hash_mismatch')
    for key in FALSE_APPROVAL_KEYS:
        if packet.get(key) is not False: b.append(f'approval_{key}_not_false')
    b.extend(scan_value(packet, label='abhe_v0_candidate_materialization_approval_packet'))
    return sorted(set(b))

def validate_candidates(data: Dict[str,Any], approval: Dict[str,Any], fresh_hash: str)->List[str]:
    b=[]
    if data.get('artifact_kind')!='abhe_v0_materialized_candidates': b.append('materialized_candidates_artifact_kind_invalid')
    if data.get('schema_version')!='abhe_v0_materialized_candidates_v0': b.append('materialized_candidates_schema_version_invalid')
    if data.get('candidate_materialized') is not True: b.append('candidate_materialized_not_true')
    if data.get('selected_case_ids_hash')!=fresh_hash or data.get('selected_case_ids_hash')!=approval.get('approved_fresh_dev_slice_hash'):
        b.append('selected_case_ids_hash_mismatch')
    for key in FALSE_CANDIDATE_KEYS:
        if data.get(key) is not False: b.append(f'materialized_candidates_{key}_not_false')
    rows=data.get('candidates')
    if not isinstance(rows, list):
        b.append('candidates_not_list'); rows=[]
    by_entry={row.get('entry_id'): row for row in rows if isinstance(row, dict)}
    if set(by_entry)!=EXPECTED_ENTRIES: b.append('materialized_candidate_entries_invalid')
    if 'unresolved_search_memory_watch_v0' in by_entry or 'search_query_or_fetch_failure_watch_v0' in by_entry or 'memory_retrieve_update_confusion_watch_v0' in by_entry:
        b.append('search_memory_watch_included')
    state=by_entry.get('state_tracking_v0', {})
    if state.get('candidate_type')!='state_summary_injection': b.append('state_tracking_candidate_type_invalid')
    if state.get('materialized') is not True: b.append('state_tracking_not_materialized')
    if state.get('activation_boundary')!='multi_turn_only_state_carryover_evidence_required': b.append('state_tracking_activation_boundary_invalid')
    state_exclusions=set(state.get('non_target_exclusions') or [])
    for required in ['single_turn','search_memory_watch','state_mutation']:
        if required not in state_exclusions: b.append(f'state_tracking_exclusion_missing:{required}')
    state_guidance=state.get('guidance_contract') or {}
    for required in ['preserve_prior_turn_entities','preserve_prior_constraints','reuse_selected_options_when_referenced','no_state_mutation']:
        if state_guidance.get(required) is not True: b.append(f'state_tracking_guidance_missing:{required}')
    hallucination=by_entry.get('hallucination_abstain_v0', {})
    if hallucination.get('candidate_type')!='evidence_boundary_verifier': b.append('hallucination_candidate_type_invalid')
    if hallucination.get('materialized') is not True: b.append('hallucination_not_materialized')
    if hallucination.get('activation_boundary')!='answerability_failure_only': b.append('hallucination_activation_boundary_invalid')
    hallucination_exclusions=set(hallucination.get('non_target_exclusions') or [])
    for required in ['valid_actionable_tool_use','sufficient_evidence_cases']:
        if required not in hallucination_exclusions: b.append(f'hallucination_exclusion_missing:{required}')
    hallucination_guidance=hallucination.get('guidance_contract') or {}
    for required in ['do_not_fabricate_without_evidence','insufficient_evidence_boundary_allowed','do_not_suppress_valid_tool_calls','track_false_abstain']:
        if hallucination_guidance.get(required) is not True: b.append(f'hallucination_guidance_missing:{required}')
    telemetry=set(hallucination.get('telemetry_required') or [])
    if 'false_abstain_candidate' not in telemetry: b.append('false_abstain_telemetry_missing')
    for path in FORBIDDEN_ARTIFACTS:
        if path.exists(): b.append(f'forbidden_candidate_artifact_present:{path}')
    b.extend(scan_value(data, label='abhe_v0_materialized_candidates'))
    return sorted(set(b))

def check(approval_packet: Path=DEFAULT_APPROVAL_PACKET, candidates_path: Path=DEFAULT_CANDIDATES, fresh_manifest_path: Path=DEFAULT_FRESH_MANIFEST)->Dict[str,Any]:
    blockers=[]; approval={}; candidates={}; fresh_hash=EXPECTED_HASH
    if fresh_manifest_path.exists():
        fresh=_load(fresh_manifest_path)
        fresh_hash=fresh.get('selected_case_ids_hash') or EXPECTED_HASH
    else:
        blockers.append('fresh_slice_manifest_missing')
    if not approval_packet.exists():
        blockers.append('candidate_materialization_approval_packet_missing')
    else:
        approval=_load(approval_packet); blockers.extend(validate_approval(approval, fresh_hash))
    if not candidates_path.exists():
        blockers.append('materialized_candidates_missing')
    else:
        candidates=_load(candidates_path); blockers.extend(validate_candidates(candidates, approval, fresh_hash))
    blockers=sorted(set(blockers))
    return {'report_scope':'abhe_v0_materialized_candidates_check','approval_packet_path':str(approval_packet),'materialized_candidates_path':str(candidates_path),'fresh_manifest_path':str(fresh_manifest_path),'approval_packet_present':approval_packet.exists(),'materialized_candidates_present':candidates_path.exists(),'candidate_materialization_approved':approval.get('authorized') is True and approval.get('approval_scope')=='candidate_materialization_only' and not [x for x in blockers if x.startswith('approval_') or x=='candidate_materialization_approval_packet_missing'],'candidate_materialized':candidates.get('candidate_materialized') is True,'selected_case_ids_hash':candidates.get('selected_case_ids_hash'),'candidate_rule_generated':candidates.get('candidate_rule_generated') is True,'candidate_yaml_generated':candidates.get('candidate_yaml_generated') is True,'candidate_jsonl_generated':candidates.get('candidate_jsonl_generated') is True,'candidate_pool_ready':candidates.get('candidate_pool_ready') is True,'execution_authorized':False,'provider_calls_authorized':False,'bfcl_generate_authorized':False,'bfcl_evaluate_authorized':False,'scorer_authorized':False,'performance_evidence':False,'abhe_v0_materialized_candidates_check_passed':not blockers,'blockers':blockers}

def main(argv: Any=None)->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--approval-packet', type=Path, default=DEFAULT_APPROVAL_PACKET); ap.add_argument('--candidates', type=Path, default=DEFAULT_CANDIDATES); ap.add_argument('--fresh-manifest', type=Path, default=DEFAULT_FRESH_MANIFEST); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try: summary=check(args.approval_packet, args.candidates, args.fresh_manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc: summary={'report_scope':'abhe_v0_materialized_candidates_check','abhe_v0_materialized_candidates_check_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.strict and not summary.get('abhe_v0_materialized_candidates_check_passed') else 0
if __name__=='__main__': raise SystemExit(main())
