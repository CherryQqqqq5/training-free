#!/usr/bin/env python3
"""Validate ABHE-v0 BFCL fresh slice review artifacts without approval or materialization."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_DATASET_REVIEW=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_review.json')
DEFAULT_CATEGORY_REVIEW=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_category_review.json')
DEFAULT_SLICE_REVIEW=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_review.json')
DEFAULT_EXCLUSION_PROOF=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_source_exclusion_proof.json')
ALLOWED_ENTRIES={'state_tracking_v0','hallucination_abstain_v0'}
FORCED_FALSE=['authorized','raw_material_committed','raw_material_persisted']


def _load(path: Path) -> Dict[str, Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path} must contain a JSON object')
    return data


def _check_false(data: Dict[str, Any], keys: List[str], label: str) -> List[str]:
    return [f'{label}_{key}_not_false' for key in keys if key in data and data.get(key) is not False]


def validate_dataset_review(data: Dict[str, Any]) -> List[str]:
    b=[]
    if data.get('artifact_kind')!='abhe_v0_bfcl_dataset_path_review': b.append('dataset_artifact_kind_invalid')
    if data.get('selected_dataset_path')!='pending_reviewer_selection': b.append('selected_dataset_path_must_remain_pending')
    if data.get('approval_required') is not True: b.append('dataset_approval_required_not_true')
    if data.get('authorized') is not False: b.append('dataset_authorized_not_false')
    if data.get('raw_material_committed') is not False: b.append('dataset_raw_material_committed_not_false')
    if not isinstance(data.get('dataset_path_candidates'), list) or not data.get('dataset_path_candidates'): b.append('dataset_path_candidates_missing')
    b.extend(scan_value(data, label='abhe_v0_bfcl_dataset_path_review'))
    return sorted(set(b))


def validate_category_review(data: Dict[str, Any]) -> List[str]:
    b=[]
    if data.get('artifact_kind')!='abhe_v0_bfcl_category_review': b.append('category_artifact_kind_invalid')
    if data.get('authorized') is not False: b.append('category_authorized_not_false')
    if data.get('raw_material_persisted') is not False: b.append('category_raw_material_persisted_not_false')
    state=set(data.get('proposed_strata_for_state_tracking_v0', []))
    halluc=set(data.get('proposed_strata_for_hallucination_abstain_v0', []))
    if not state: b.append('state_tracking_strata_missing')
    if not halluc: b.append('hallucination_strata_missing')
    if any('memory' in item or 'web_search' in item for item in state | halluc): b.append('search_memory_watch_strata_mixed_into_top2')
    b.extend(scan_value(data, label='abhe_v0_bfcl_category_review'))
    return sorted(set(b))


def validate_slice_review(data: Dict[str, Any]) -> List[str]:
    b=[]
    if data.get('artifact_kind')!='abhe_v0_bfcl_fresh_dev_slice_review': b.append('slice_artifact_kind_invalid')
    if data.get('approval_status')!='pending': b.append('slice_approval_status_not_pending')
    for key in ['authorized','fresh_dev_slice_materialized','source_160_compact_cases_reused_for_validation','raw_cases_persisted','gold_expected_persisted','scorer_diff_persisted','performance_evidence','holdout_authorized','full_suite_authorized']:
        if data.get(key) is not False: b.append(f'slice_{key}_not_false')
    if data.get('archive_seed_source_excluded') is not True: b.append('slice_archive_seed_source_excluded_not_true')
    entries=set(data.get('selected_entry_ids', []))
    if entries != ALLOWED_ENTRIES: b.append('slice_selected_entry_ids_invalid')
    count=data.get('selected_case_count_per_entry_proposed')
    if not isinstance(count, int) or count < 1 or count > 20: b.append('slice_case_count_per_entry_out_of_bounds')
    if data.get('proposed_selected_case_ids_hash') != 'pending_until_reviewer_selects_dataset_path' and not str(data.get('proposed_selected_case_ids_hash','')).startswith('sha256:'):
        b.append('slice_proposed_hash_invalid')
    b.extend(scan_value(data, label='abhe_v0_bfcl_fresh_dev_slice_review'))
    return sorted(set(b))


def validate_exclusion_proof(data: Dict[str, Any]) -> List[str]:
    b=[]
    if data.get('artifact_kind')!='abhe_v0_bfcl_source_exclusion_proof': b.append('proof_artifact_kind_invalid')
    if data.get('raw_material_persisted') is not False: b.append('proof_raw_material_persisted_not_false')
    if data.get('source_160_compact_cases_reused_for_validation') is not False: b.append('proof_source_160_reused_not_false')
    if data.get('archive_seed_source_excluded') is not True: b.append('proof_archive_seed_source_excluded_not_true')
    status=data.get('overlap_check_status')
    if status == 'computed':
        if data.get('overlap_count') != 0: b.append('proof_overlap_count_not_zero')
        if data.get('overlap_hashes') not in ([], None): b.append('proof_overlap_hashes_not_empty')
    elif status == 'blocked':
        blockers=set(data.get('blockers', []))
        if not blockers: b.append('proof_blocked_without_blockers')
        if 'bfcl_dataset_path_not_selected' not in blockers and 'discovery_source_hash_unavailable' not in blockers:
            b.append('proof_blockers_missing_expected_fail_closed_reason')
    else:
        b.append('proof_overlap_check_status_invalid')
    b.extend(scan_value(data, label='abhe_v0_bfcl_source_exclusion_proof'))
    return sorted(set(b))


def check(dataset_review: Path=DEFAULT_DATASET_REVIEW, category_review: Path=DEFAULT_CATEGORY_REVIEW, slice_review: Path=DEFAULT_SLICE_REVIEW, exclusion_proof: Path=DEFAULT_EXCLUSION_PROOF) -> Dict[str, Any]:
    blockers=[]; summaries={}
    for name,path,validator in [
        ('dataset_path_review',dataset_review,validate_dataset_review),
        ('category_review',category_review,validate_category_review),
        ('fresh_dev_slice_review',slice_review,validate_slice_review),
        ('source_exclusion_proof',exclusion_proof,validate_exclusion_proof),
    ]:
        if not path.exists():
            blockers.append(f'{name}_missing:{path}')
            continue
        data=_load(path); vb=validator(data); blockers.extend([f'{name}:{x}' for x in vb]); summaries[name]={'path':str(path),'blockers':vb,'artifact_kind':data.get('artifact_kind')}
    execution_ready_blockers=[]
    proof=_load(exclusion_proof) if exclusion_proof.exists() else {}
    if proof.get('overlap_check_status')!='computed': execution_ready_blockers.append('source_exclusion_proof_not_computed')
    slice_data=_load(slice_review) if slice_review.exists() else {}
    if slice_data.get('fresh_dev_slice_materialized') is not True: execution_ready_blockers.append('fresh_dev_slice_not_materialized')
    return {'report_scope':'abhe_v0_bfcl_fresh_slice_review_check','artifact_kind':'abhe_v0_bfcl_fresh_slice_review_check','abhe_v0_bfcl_fresh_slice_review_passed':not blockers,'abhe_v0_bfcl_fresh_slice_review_execution_ready':False,'authorized':False,'fresh_dev_slice_materialized':False,'performance_evidence':False,'component_summaries':summaries,'execution_ready_blockers':sorted(set(execution_ready_blockers)),'blockers':sorted(set(blockers))}


def main(argv: Any=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try: summary=check()
    except (OSError, ValueError, json.JSONDecodeError) as exc: summary={'report_scope':'abhe_v0_bfcl_fresh_slice_review_check','abhe_v0_bfcl_fresh_slice_review_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.strict and not summary.get('abhe_v0_bfcl_fresh_slice_review_passed') else 0
if __name__=='__main__': raise SystemExit(main())
