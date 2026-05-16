#!/usr/bin/env python3
"""Validate ABHE-v0 BFCL fresh slice review artifacts without approval or materialization."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_DATASET_SELECTION=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_selection.json')
DEFAULT_DATASET_REVIEW=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_review.json')
DEFAULT_CATEGORY_REVIEW=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_category_review.json')
DEFAULT_SLICE_REVIEW=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_review.json')
DEFAULT_EXCLUSION_PROOF=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_source_exclusion_proof.json')
ALLOWED_ENTRIES={'state_tracking_v0','hallucination_abstain_v0'}
ALLOWED_COMPACT_CASE_FIELDS={'entry_id','bfcl_category','source_file_hash','case_stable_hash','case_row_index_hash','case_identifier_hash'}
APPROVED_DATASET_PATH='.venv/lib/python3.10/site-packages/bfcl_eval/data'


def _load(path: Path) -> Dict[str, Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path} must contain a JSON object')
    return data


def _check_hash(value: Any) -> bool:
    return isinstance(value, str) and value.startswith('sha256:') and len(value) == len('sha256:') + 64


def validate_dataset_selection(data: Dict[str, Any]) -> List[str]:
    b=[]
    if data.get('artifact_kind')!='abhe_v0_bfcl_dataset_path_selection': b.append('selection_artifact_kind_invalid')
    if data.get('selected_dataset_path')!=APPROVED_DATASET_PATH: b.append('selection_selected_dataset_path_invalid')
    if data.get('authorized_for')!='fresh_slice_hash_and_overlap_proof_only': b.append('selection_authorized_for_invalid')
    for key in ['authorized','fresh_dev_slice_materialization_authorized','bfcl_generate_authorized','bfcl_evaluate_authorized','scorer_authorized','candidate_generation_authorized','performance_evidence','raw_material_committed']:
        if data.get(key) is not False: b.append(f'selection_{key}_not_false')
    b.extend(scan_value(data, label='abhe_v0_bfcl_dataset_path_selection'))
    return sorted(set(b))


def validate_dataset_review(data: Dict[str, Any]) -> List[str]:
    b=[]
    if data.get('artifact_kind')!='abhe_v0_bfcl_dataset_path_review': b.append('dataset_artifact_kind_invalid')
    selected=data.get('selected_dataset_path')
    if selected not in ('pending_reviewer_selection', APPROVED_DATASET_PATH): b.append('selected_dataset_path_invalid')
    if selected == APPROVED_DATASET_PATH and data.get('selected_for')!='fresh_slice_hash_and_overlap_proof_only': b.append('dataset_selected_for_invalid')
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
    proposed_hash=data.get('proposed_selected_case_ids_hash')
    if proposed_hash != 'pending_until_reviewer_selects_dataset_path' and not _check_hash(proposed_hash): b.append('slice_proposed_hash_invalid')
    if data.get('case_keys_persisted') is True:
        cases=data.get('proposed_compact_case_identifiers')
        if not isinstance(cases, list) or len(cases) != 20: b.append('slice_compact_case_identifier_count_invalid')
        else:
            by_entry={entry:0 for entry in ALLOWED_ENTRIES}
            for idx, item in enumerate(cases):
                if not isinstance(item, dict):
                    b.append(f'slice_compact_case_{idx}_not_object'); continue
                extra=set(item)-ALLOWED_COMPACT_CASE_FIELDS
                if extra: b.append(f'slice_compact_case_{idx}_extra_fields')
                if item.get('entry_id') not in ALLOWED_ENTRIES: b.append(f'slice_compact_case_{idx}_entry_invalid')
                else: by_entry[item['entry_id']] += 1
                for key in ['source_file_hash','case_stable_hash','case_row_index_hash']:
                    if not _check_hash(item.get(key)): b.append(f'slice_compact_case_{idx}_{key}_invalid')
                if 'case_identifier_hash' in item and not _check_hash(item.get('case_identifier_hash')): b.append(f'slice_compact_case_{idx}_case_identifier_hash_invalid')
            if set(by_entry.values()) != {10}: b.append('slice_compact_case_count_by_entry_invalid')
    b.extend(scan_value(data, label='abhe_v0_bfcl_fresh_dev_slice_review'))
    return sorted(set(b))


def validate_exclusion_proof(data: Dict[str, Any]) -> List[str]:
    b=[]
    if data.get('artifact_kind')!='abhe_v0_bfcl_source_exclusion_proof': b.append('proof_artifact_kind_invalid')
    if data.get('raw_material_persisted') is not False: b.append('proof_raw_material_persisted_not_false')
    if data.get('performance_evidence') is not False: b.append('proof_performance_evidence_not_false')
    if data.get('source_160_compact_cases_reused_for_validation') is not False: b.append('proof_source_160_reused_not_false')
    if data.get('archive_seed_source_excluded') is not True: b.append('proof_archive_seed_source_excluded_not_true')
    status=data.get('overlap_check_status')
    if status in {'complete','computed'}:
        if data.get('discovery_source_hash_count') != 160: b.append('proof_discovery_source_hash_count_not_160')
        if data.get('candidate_case_hash_count') != 20: b.append('proof_candidate_case_hash_count_not_20')
        if data.get('overlap_count') != 0: b.append('proof_overlap_count_not_zero')
        if data.get('overlap_hashes') != []: b.append('proof_overlap_hashes_not_empty')
        if data.get('blockers') not in ([], None): b.append('proof_complete_with_blockers')
    elif status == 'blocked':
        blockers=set(data.get('blockers', []))
        if not blockers: b.append('proof_blocked_without_blockers')
        if 'bfcl_dataset_path_not_selected' not in blockers and 'discovery_source_hash_unavailable' not in blockers:
            b.append('proof_blockers_missing_expected_fail_closed_reason')
    else:
        b.append('proof_overlap_check_status_invalid')
    b.extend(scan_value(data, label='abhe_v0_bfcl_source_exclusion_proof'))
    return sorted(set(b))


def check(dataset_selection: Path=DEFAULT_DATASET_SELECTION, dataset_review: Path=DEFAULT_DATASET_REVIEW, category_review: Path=DEFAULT_CATEGORY_REVIEW, slice_review: Path=DEFAULT_SLICE_REVIEW, exclusion_proof: Path=DEFAULT_EXCLUSION_PROOF) -> Dict[str, Any]:
    blockers=[]; summaries={}
    checks=[('dataset_path_selection',dataset_selection,validate_dataset_selection),('dataset_path_review',dataset_review,validate_dataset_review),('category_review',category_review,validate_category_review),('fresh_dev_slice_review',slice_review,validate_slice_review),('source_exclusion_proof',exclusion_proof,validate_exclusion_proof)]
    for name,path,validator in checks:
        if not path.exists():
            if name == 'dataset_path_selection':
                continue
            blockers.append(f'{name}_missing:{path}')
            continue
        data=_load(path); vb=validator(data); blockers.extend([f'{name}:{x}' for x in vb]); summaries[name]={'path':str(path),'blockers':vb,'artifact_kind':data.get('artifact_kind')}
    execution_ready_blockers=[]
    proof=_load(exclusion_proof) if exclusion_proof.exists() else {}
    if proof.get('overlap_check_status') not in {'complete','computed'} or proof.get('overlap_count') != 0:
        execution_ready_blockers.append('source_exclusion_proof_not_computed')
    slice_data=_load(slice_review) if slice_review.exists() else {}
    if slice_data.get('fresh_dev_slice_materialized') is not True:
        execution_ready_blockers.append('fresh_dev_slice_not_materialized')
    return {'report_scope':'abhe_v0_bfcl_fresh_slice_review_check','artifact_kind':'abhe_v0_bfcl_fresh_slice_review_check','abhe_v0_bfcl_fresh_slice_review_passed':not blockers,'abhe_v0_bfcl_fresh_slice_review_execution_ready':False,'authorized':False,'fresh_dev_slice_materialized':False,'performance_evidence':False,'component_summaries':summaries,'execution_ready_blockers':sorted(set(execution_ready_blockers)),'blockers':sorted(set(blockers))}


def main(argv: Any=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try: summary=check()
    except (OSError, ValueError, json.JSONDecodeError) as exc: summary={'report_scope':'abhe_v0_bfcl_fresh_slice_review_check','abhe_v0_bfcl_fresh_slice_review_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.strict and not summary.get('abhe_v0_bfcl_fresh_slice_review_passed') else 0
if __name__=='__main__': raise SystemExit(main())
