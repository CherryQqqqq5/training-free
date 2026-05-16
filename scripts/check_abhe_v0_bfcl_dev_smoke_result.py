#!/usr/bin/env python3
"""Check ABHE-v0 BFCL dev smoke dry-run manifest or compact result."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from scripts.check_abhe_no_leakage_boundary import scan_value
DEFAULT_MANIFEST=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_dry_run_manifest.json')
DEFAULT_RESULT=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_result.json')
EXPECTED_HASH='sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f'

def _load(path: Path)->Dict[str,Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path} must contain a JSON object')
    return data

def validate_dry_run(m: Dict[str,Any])->List[str]:
    b=[]
    if m.get('artifact_kind')!='abhe_v0_bfcl_dev_smoke_dry_run_manifest': b.append('manifest_artifact_kind_invalid')
    if m.get('dry_run') is not True: b.append('dry_run_not_true')
    for k in ['provider_calls_made','bfcl_generate_called','bfcl_evaluate_called','scorer_called','candidate_generated','candidate_jsonl_created','performance_evidence','execution_started']:
        if m.get(k) is not False: b.append(f'{k}_not_false')
    b.extend(scan_value(m, label='abhe_v0_bfcl_dev_smoke_dry_run_manifest'))
    return sorted(set(b))

def validate_result(r: Dict[str,Any])->List[str]:
    b=[]
    if r.get('artifact_kind')!='abhe_v0_bfcl_dev_smoke_result': b.append('result_artifact_kind_invalid')
    if r.get('compact_only') is not True: b.append('compact_only_not_true')
    if r.get('selected_case_ids_hash') != EXPECTED_HASH: b.append('selected_case_ids_hash_invalid')
    for k in ['baseline_arm_complete','candidate_arm_complete','provider_model_protocol_match','raw_material_absent','provider_calls_made','bfcl_generate_called','bfcl_evaluate_called','scorer_called']:
        if r.get(k) is not True: b.append(f'{k}_not_true')
    for k in ['holdout_touched','full_suite_touched','performance_claim_authorized','performance_evidence','raw_provider_payload_committed','raw_bfcl_result_tree_committed','gold_expected_committed','scorer_diff_committed']:
        if r.get(k) is not False: b.append(f'{k}_not_false')
    for arm_key in ['baseline_compact_metrics','candidate_compact_metrics']:
        metrics=r.get(arm_key)
        if not isinstance(metrics, dict):
            b.append(f'{arm_key}_missing')
            continue
        if metrics.get('case_count') != 20: b.append(f'{arm_key}_case_count_not_20')
        passed=metrics.get('passed_count')
        if not isinstance(passed, int) or passed < 0 or passed > 20: b.append(f'{arm_key}_passed_count_invalid')
    b.extend(scan_value(r, label='abhe_v0_bfcl_dev_smoke_result'))
    return sorted(set(b))

def check(*, dry_run_manifest: bool=False, path: Path=DEFAULT_RESULT)->Dict[str,Any]:
    target=DEFAULT_MANIFEST if dry_run_manifest else path
    if not target.exists(): return {'report_scope':'abhe_v0_bfcl_dev_smoke_result_check','path':str(target),'present':False,'abhe_v0_bfcl_dev_smoke_result_check_passed':False,'blockers':['dev_smoke_artifact_missing']}
    data=_load(target); b=validate_dry_run(data) if dry_run_manifest else validate_result(data)
    return {'report_scope':'abhe_v0_bfcl_dev_smoke_result_check','path':str(target),'present':True,'dry_run_manifest':dry_run_manifest,'abhe_v0_bfcl_dev_smoke_result_check_passed':not b,'provider_calls_made':data.get('provider_calls_made'),'bfcl_generate_called':data.get('bfcl_generate_called'),'bfcl_evaluate_called':data.get('bfcl_evaluate_called'),'scorer_called':data.get('scorer_called'),'performance_evidence':data.get('performance_evidence'),'blockers':b}

def main(argv: Any=None)->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--result', type=Path, default=DEFAULT_RESULT); ap.add_argument('--dry-run-manifest', action='store_true'); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try: s=check(dry_run_manifest=args.dry_run_manifest, path=args.result)
    except (OSError, ValueError, json.JSONDecodeError) as exc: s={'report_scope':'abhe_v0_bfcl_dev_smoke_result_check','abhe_v0_bfcl_dev_smoke_result_check_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(s, sort_keys=True) if args.compact else json.dumps(s, indent=2, sort_keys=True))
    return 1 if args.strict and not s.get('abhe_v0_bfcl_dev_smoke_result_check_passed') else 0
if __name__=='__main__': raise SystemExit(main())
