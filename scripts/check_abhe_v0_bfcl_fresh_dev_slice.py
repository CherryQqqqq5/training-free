#!/usr/bin/env python3
"""Validate the ABHE-v0 BFCL fresh dev slice plan and compact manifest."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from scripts.build_abhe_v0_bfcl_fresh_dev_slice import DEFAULT_OUTPUT, TARGET_ENTRIES
from scripts.check_abhe_fresh_dev_slice_approval_packet import check as check_fresh_slice_approval
from scripts.check_abhe_no_leakage_boundary import scan_value

DEFAULT_MANIFEST=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_manifest.json')
DEFAULT_EXCLUSION_PROOF=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_source_exclusion_proof.json')
ALLOWED_CASE_FIELDS={'entry_id','bfcl_category','source_file_hash','case_stable_hash','case_row_index_hash','case_identifier_hash'}
EXPECTED_CASE_COUNT_BY_ENTRY={'state_tracking_v0':10,'hallucination_abstain_v0':10}
EXPECTED_CASE_COUNT_BY_CATEGORY={'multi_turn_base':3,'multi_turn_long_context':3,'multi_turn_miss_func':2,'multi_turn_miss_param':2,'irrelevance':4,'live_irrelevance':3,'live_relevance':3}
FALSE_KEYS=['source_160_compact_cases_reused_for_validation','performance_evidence','holdout_touched','full_suite_touched','provider_calls_made','bfcl_generate_called','bfcl_evaluate_called','scorer_called']
MANIFEST_FALSE_KEYS=['raw_cases_persisted','gold_expected_persisted','scorer_diff_persisted','provider_calls_authorized','bfcl_generate_authorized','bfcl_evaluate_authorized','scorer_authorized','candidate_generation_authorized','candidate_materialization_authorized','execution_authorized','performance_evidence','holdout_authorized','full_suite_authorized','source_160_compact_cases_reused_for_validation']

def _load(path: Path) -> Dict[str, Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path} must contain a JSON object')
    return data

def _hash_ok(value: Any) -> bool:
    return isinstance(value, str) and value.startswith('sha256:') and len(value)==71

def validate_plan(plan: Dict[str, Any]) -> List[str]:
    b=[]
    if plan.get('artifact_kind')!='abhe_v0_bfcl_fresh_dev_slice_plan': b.append('artifact_kind_invalid')
    if plan.get('approval_required') is not True: b.append('approval_required_not_true')
    if plan.get('source_dataset')!='BFCL': b.append('source_dataset_not_bfcl')
    if plan.get('entry_ids')!=TARGET_ENTRIES: b.append('entry_ids_invalid')
    if plan.get('target_case_count_per_entry')!='10_to_20': b.append('target_case_count_per_entry_invalid')
    for k in FALSE_KEYS:
        if plan.get(k) is not False: b.append(f'{k}_not_false')
    if plan.get('archive_seed_source_excluded') is not True: b.append('archive_seed_source_excluded_not_true')
    if plan.get('raw_material_absent') is not True: b.append('raw_material_absent_not_true')
    if not plan.get('selected_case_ids_hash'): b.append('selected_case_ids_hash_missing')
    if plan.get('fresh_dev_slice_materialized') is True:
        if not _hash_ok(plan.get('selected_case_ids_hash')): b.append('selected_case_ids_hash_invalid_after_materialization')
        if plan.get('approval_authorized') is not True: b.append('approval_authorized_not_true_after_materialization')
    else:
        if plan.get('selected_case_ids_hash')!='pending_until_materialized': b.append('selected_case_ids_hash_should_be_pending_before_materialization')
    proposed=plan.get('proposed_selected_case_ids_hash')
    if proposed and proposed != 'pending_until_reviewer_selects_dataset_path' and not _hash_ok(proposed): b.append('proposed_selected_case_ids_hash_invalid')
    b.extend(scan_value(plan, label='abhe_v0_bfcl_fresh_dev_slice_plan'))
    return sorted(set(b))

def validate_manifest(manifest: Dict[str, Any], approval: Dict[str, Any], proof: Dict[str, Any]) -> List[str]:
    b=[]
    if manifest.get('artifact_kind')!='abhe_v0_bfcl_fresh_dev_slice_manifest': b.append('manifest_artifact_kind_invalid')
    if manifest.get('schema_version')!='abhe_v0_bfcl_fresh_dev_slice_manifest_v0': b.append('manifest_schema_version_invalid')
    if manifest.get('fresh_dev_slice_materialized') is not True: b.append('manifest_materialized_not_true')
    if manifest.get('selected_dataset_path')!='.venv/lib/python3.10/site-packages/bfcl_eval/data': b.append('manifest_dataset_path_invalid')
    if manifest.get('selected_case_ids_hash') != approval.get('approved_fresh_dev_slice_hash'): b.append('manifest_hash_mismatch_approval')
    if manifest.get('selected_case_count') != 20: b.append('manifest_selected_case_count_not_20')
    if manifest.get('case_count_by_entry') != EXPECTED_CASE_COUNT_BY_ENTRY: b.append('manifest_case_count_by_entry_invalid')
    if manifest.get('case_count_by_category') != EXPECTED_CASE_COUNT_BY_CATEGORY: b.append('manifest_case_count_by_category_invalid')
    if proof.get('overlap_count') != 0 or manifest.get('overlap_count') != 0: b.append('manifest_overlap_count_not_zero')
    if manifest.get('archive_seed_source_excluded') is not True: b.append('manifest_archive_seed_source_excluded_not_true')
    for k in MANIFEST_FALSE_KEYS:
        if manifest.get(k) is not False: b.append(f'manifest_{k}_not_false')
    cases=manifest.get('selected_compact_case_identifiers')
    if not isinstance(cases, list) or len(cases)!=20:
        b.append('manifest_selected_compact_case_identifier_count_invalid')
    else:
        by_entry={entry:0 for entry in EXPECTED_CASE_COUNT_BY_ENTRY}
        for idx,item in enumerate(cases):
            if not isinstance(item, dict):
                b.append(f'manifest_case_{idx}_not_object'); continue
            extra=set(item)-ALLOWED_CASE_FIELDS
            if extra: b.append(f'manifest_case_{idx}_extra_fields')
            if item.get('entry_id') not in EXPECTED_CASE_COUNT_BY_ENTRY: b.append(f'manifest_case_{idx}_entry_invalid')
            else: by_entry[item['entry_id']]+=1
            for key in ['source_file_hash','case_stable_hash','case_row_index_hash']:
                if not _hash_ok(item.get(key)): b.append(f'manifest_case_{idx}_{key}_invalid')
            if 'case_identifier_hash' in item and not _hash_ok(item.get('case_identifier_hash')): b.append(f'manifest_case_{idx}_case_identifier_hash_invalid')
        if by_entry != EXPECTED_CASE_COUNT_BY_ENTRY: b.append('manifest_case_count_by_entry_from_rows_invalid')
    b.extend(scan_value(manifest, label='abhe_v0_bfcl_fresh_dev_slice_manifest'))
    return sorted(set(b))

def check(path: Path = DEFAULT_OUTPUT, manifest_path: Path = DEFAULT_MANIFEST) -> Dict[str, Any]:
    if not path.exists(): return {'report_scope':'abhe_v0_bfcl_fresh_dev_slice_check','plan_path':str(path),'plan_present':False,'abhe_v0_bfcl_fresh_dev_slice_check_passed':False,'blockers':['fresh_dev_slice_plan_missing']}
    plan=_load(path); blockers=validate_plan(plan); eb=list(plan.get('execution_blockers', []))
    approval_summary=check_fresh_slice_approval(); approval={}
    if approval_summary.get('abhe_fresh_dev_slice_approval_packet_passed'):
        approval=_load(Path(approval_summary['packet_path']))
    else:
        blockers += [f"approval:{x}" for x in approval_summary.get('blockers', [])]
    manifest_present=manifest_path.exists(); manifest={}
    if plan.get('fresh_dev_slice_materialized') is True:
        if not manifest_present:
            blockers.append('fresh_dev_slice_manifest_missing')
        else:
            manifest=_load(manifest_path); proof=_load(DEFAULT_EXCLUSION_PROOF)
            blockers += [f'manifest:{x}' for x in validate_manifest(manifest, approval, proof)]
    required=set() if plan.get('fresh_dev_slice_materialized') is True else {'fresh_dev_slice_approval_missing'}
    allowed={'bfcl_dataset_path_missing','fresh_dev_slice_approval_missing'}
    passed = not blockers and required.issubset(set(eb)) and set(eb).issubset(allowed)
    return {'report_scope':'abhe_v0_bfcl_fresh_dev_slice_check','plan_path':str(path),'plan_present':True,'manifest_path':str(manifest_path),'manifest_present':manifest_present,'abhe_v0_bfcl_fresh_dev_slice_check_passed':passed,'fresh_dev_slice_materialized':plan.get('fresh_dev_slice_materialized') is True,'selected_case_ids_hash':plan.get('selected_case_ids_hash'),'source_160_compact_cases_reused_for_validation':plan.get('source_160_compact_cases_reused_for_validation'),'archive_seed_source_excluded':plan.get('archive_seed_source_excluded'),'execution_blockers':sorted(set(eb)),'approval_packet_passed':approval_summary.get('abhe_fresh_dev_slice_approval_packet_passed') is True,'blockers':sorted(set(blockers))}

def main(argv: Any=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--plan', type=Path, default=DEFAULT_OUTPUT); ap.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try: summary=check(args.plan, args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc: summary={'report_scope':'abhe_v0_bfcl_fresh_dev_slice_check','abhe_v0_bfcl_fresh_dev_slice_check_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.strict and not summary.get('abhe_v0_bfcl_fresh_dev_slice_check_passed') else 0
if __name__=='__main__': raise SystemExit(main())
