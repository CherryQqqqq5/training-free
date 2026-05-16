#!/usr/bin/env python3
"""Validate ABHE-v0 same-slice rerun stability artifact."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from typing import Any, Dict, List
from scripts.check_abhe_no_leakage_boundary import scan_value
DEFAULT=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_same_slice_rerun_stability.json')
EXPECTED_HASH='sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f'
def _load(p:Path)->Dict[str,Any]:
    d=json.loads(p.read_text(encoding='utf-8'))
    if not isinstance(d,dict): raise ValueError('artifact must be object')
    return d
def validate(d:Dict[str,Any])->List[str]:
    b=[]
    if d.get('artifact_kind')!='abhe_v0_bfcl_same_slice_rerun_stability': b.append('artifact_kind_invalid')
    if d.get('schema_version')!='abhe_v0_bfcl_same_slice_rerun_stability_v0': b.append('schema_version_invalid')
    if d.get('bounded_dev_smoke_only') is not True: b.append('bounded_dev_smoke_only_not_true')
    if d.get('selected_case_ids_hash')!=EXPECTED_HASH: b.append('selected_case_ids_hash_invalid')
    if d.get('same_slice_rerun_stability_passed') is not True: b.append('same_slice_rerun_stability_not_passed')
    if d.get('same_slice_rerun_stable') is not True: b.append('same_slice_rerun_not_stable')
    for key in ['raw_material_absent']:
        if d.get(key) is not True: b.append(f'{key}_not_true')
    for key in ['raw_provider_payload_committed','raw_bfcl_result_tree_committed','gold_expected_committed','scorer_diff_committed','performance_evidence','holdout_touched','full_suite_touched','archive_updated']:
        if d.get(key) is not False: b.append(f'{key}_not_false')
    if not isinstance(d.get('prior_snapshot'),dict) or not isinstance(d.get('rerun_snapshot'),dict): b.append('snapshots_missing')
    b.extend(scan_value(d,label='abhe_v0_bfcl_same_slice_rerun_stability'))
    return sorted(set(b))
def check(path:Path=DEFAULT)->Dict[str,Any]:
    if not path.exists(): return {'report_scope':'abhe_v0_bfcl_same_slice_rerun_stability_check','artifact_present':False,'same_slice_rerun_stability_check_passed':False,'blockers':['same_slice_rerun_stability_missing']}
    d=_load(path); b=validate(d)
    return {'report_scope':'abhe_v0_bfcl_same_slice_rerun_stability_check','artifact_present':True,'same_slice_rerun_stability_check_passed':not b,'same_slice_rerun_stable':d.get('same_slice_rerun_stable'),'baseline_passed_count_abs_delta':d.get('baseline_passed_count_abs_delta'),'candidate_passed_count_abs_delta':d.get('candidate_passed_count_abs_delta'),'performance_evidence':d.get('performance_evidence'),'blockers':b}
def main(argv:Any=None)->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--artifact', type=Path, default=DEFAULT); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try: r=check(args.artifact)
    except Exception as exc: r={'report_scope':'abhe_v0_bfcl_same_slice_rerun_stability_check','same_slice_rerun_stability_check_passed':False,'blockers':[f'load_failed:{exc.__class__.__name__}']}
    print(json.dumps(r,sort_keys=True) if args.compact else json.dumps(r,indent=2,sort_keys=True))
    return 1 if args.strict and not r.get('same_slice_rerun_stability_check_passed') else 0
if __name__=='__main__': raise SystemExit(main())
