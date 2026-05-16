#!/usr/bin/env python3
"""Validate the ABHE-v0 BFCL fresh dev slice plan without materializing it."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from scripts.build_abhe_v0_bfcl_fresh_dev_slice import DEFAULT_OUTPUT, TARGET_ENTRIES
from scripts.check_abhe_no_leakage_boundary import scan_value

def _load(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path} must contain a JSON object')
    return data

def validate_plan(plan: Dict[str, Any]) -> List[str]:
    b=[]
    if plan.get('artifact_kind')!='abhe_v0_bfcl_fresh_dev_slice_plan': b.append('artifact_kind_invalid')
    if plan.get('approval_required') is not True: b.append('approval_required_not_true')
    if plan.get('fresh_dev_slice_materialized') is not False: b.append('fresh_dev_slice_materialized_must_remain_false_without_approval')
    if plan.get('source_dataset')!='BFCL': b.append('source_dataset_not_bfcl')
    if plan.get('entry_ids')!=TARGET_ENTRIES: b.append('entry_ids_invalid')
    if plan.get('target_case_count_per_entry')!='10_to_20': b.append('target_case_count_per_entry_invalid')
    for k in ['source_160_compact_cases_reused_for_validation','performance_evidence','holdout_touched','full_suite_touched','provider_calls_made','bfcl_generate_called','bfcl_evaluate_called','scorer_called']:
        if plan.get(k) is not False: b.append(f'{k}_not_false')
    if plan.get('archive_seed_source_excluded') is not True: b.append('archive_seed_source_excluded_not_true')
    if plan.get('raw_material_absent') is not True: b.append('raw_material_absent_not_true')
    if not plan.get('selected_case_ids_hash'): b.append('selected_case_ids_hash_missing')
    if plan.get('fresh_dev_slice_materialized') is False and plan.get('selected_case_ids_hash')!='pending_until_materialized': b.append('selected_case_ids_hash_should_be_pending_before_materialization')
    proposed=plan.get('proposed_selected_case_ids_hash')
    if proposed and proposed != 'pending_until_reviewer_selects_dataset_path' and not str(proposed).startswith('sha256:'): b.append('proposed_selected_case_ids_hash_invalid')
    b.extend(scan_value(plan, label='abhe_v0_bfcl_fresh_dev_slice_plan'))
    return sorted(set(b))

def check(path: Path = DEFAULT_OUTPUT) -> Dict[str, Any]:
    if not path.exists(): return {'report_scope':'abhe_v0_bfcl_fresh_dev_slice_check','plan_path':str(path),'plan_present':False,'abhe_v0_bfcl_fresh_dev_slice_check_passed':False,'blockers':['fresh_dev_slice_plan_missing']}
    plan=_load(path); blockers=validate_plan(plan); eb=list(plan.get('execution_blockers', []))
    required={'fresh_dev_slice_approval_missing'}
    allowed={'bfcl_dataset_path_missing','fresh_dev_slice_approval_missing'}
    passed = not blockers and required.issubset(set(eb)) and set(eb).issubset(allowed) and plan.get('fresh_dev_slice_materialized') is False
    return {'report_scope':'abhe_v0_bfcl_fresh_dev_slice_check','plan_path':str(path),'plan_present':True,'abhe_v0_bfcl_fresh_dev_slice_check_passed':passed,'fresh_dev_slice_materialized':plan.get('fresh_dev_slice_materialized') is True,'selected_case_ids_hash':plan.get('selected_case_ids_hash'),'source_160_compact_cases_reused_for_validation':plan.get('source_160_compact_cases_reused_for_validation'),'archive_seed_source_excluded':plan.get('archive_seed_source_excluded'),'execution_blockers':sorted(set(eb)),'blockers':blockers}

def main(argv: Any=None) -> int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--plan', type=Path, default=DEFAULT_OUTPUT); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try: summary=check(args.plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc: summary={'report_scope':'abhe_v0_bfcl_fresh_dev_slice_check','abhe_v0_bfcl_fresh_dev_slice_check_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    return 1 if args.strict and not summary.get('abhe_v0_bfcl_fresh_dev_slice_check_passed') else 0
if __name__=='__main__': raise SystemExit(main())
