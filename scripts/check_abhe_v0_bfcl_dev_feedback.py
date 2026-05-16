#!/usr/bin/env python3
"""Check compact ABHE-v0 BFCL dev feedback schema and records."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict, List
from scripts.check_abhe_no_leakage_boundary import scan_value
DEFAULT_SCHEMA=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.schema.json')
DEFAULT_FEEDBACK=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.json')
REQUIRED_FIELDS=['entry_id','case_list_hash','baseline_accuracy','candidate_accuracy','target_bucket_reduction','fixed_count','regressed_count','net_fixed','non_target_regression_count','false_abstain_count','valid_tool_call_suppression_count','activation_precision','activation_recall','cost_delta_pct','latency_delta_pct','leakage_count','boundary_violation_count','provider_model_protocol_match','fresh_slice_hash_match','candidate_approved','raw_material_absent','holdout_touched','full_suite_touched','performance_claim_authorized']

def build_schema()->Dict[str,Any]:
    props={f:{} for f in REQUIRED_FIELDS}
    return {'$schema':'https://json-schema.org/draft/2020-12/schema','title':'ABHE-v0 BFCL compact dev feedback','type':'object','required':['artifact_kind','schema_version','bounded_dev_smoke_only','performance_evidence','feedback_rows'],'additionalProperties':False,'properties':{'artifact_kind':{'const':'abhe_v0_bfcl_dev_feedback'},'schema_version':{'const':'abhe_v0_bfcl_dev_feedback_v0'},'bounded_dev_smoke_only':{'const':True},'performance_evidence':{'const':False},'feedback_rows':{'type':'array','items':{'type':'object','required':REQUIRED_FIELDS,'additionalProperties':False,'properties':props}}}}

def write_schema(path: Path=DEFAULT_SCHEMA)->None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(build_schema(), indent=2, sort_keys=True)+'\n', encoding='utf-8')

def _load(path: Path)->Dict[str,Any]:
    data=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path} must contain a JSON object')
    return data

def validate_feedback(fb: Dict[str,Any])->List[str]:
    b=[]
    if fb.get('artifact_kind')!='abhe_v0_bfcl_dev_feedback': b.append('artifact_kind_invalid')
    if fb.get('bounded_dev_smoke_only') is not True: b.append('bounded_dev_smoke_only_not_true')
    if fb.get('performance_evidence') is not False: b.append('performance_evidence_not_false')
    rows=fb.get('feedback_rows')
    if not isinstance(rows, list) or not rows: b.append('feedback_rows_missing'); rows=[]
    for i,row in enumerate(rows):
        for field in REQUIRED_FIELDS:
            if field not in row: b.append(f'row_{i}_missing_{field}')
        for field in ['holdout_touched','full_suite_touched','performance_claim_authorized']:
            if row.get(field) is not False: b.append(f'row_{i}_{field}_not_false')
        if row.get('raw_material_absent') is not True: b.append(f'row_{i}_raw_material_absent_not_true')
    b.extend(scan_value(fb, label='abhe_v0_bfcl_dev_feedback'))
    return sorted(set(b))

def check(*, schema_only: bool=False, schema_path: Path=DEFAULT_SCHEMA, feedback_path: Path=DEFAULT_FEEDBACK)->Dict[str,Any]:
    if not schema_path.exists(): write_schema(schema_path)
    schema=_load(schema_path); sb=scan_value(schema, label='abhe_v0_bfcl_dev_feedback_schema')
    if schema_only: return {'report_scope':'abhe_v0_bfcl_dev_feedback_check','schema_path':str(schema_path),'schema_only':True,'abhe_v0_bfcl_dev_feedback_check_passed':not sb,'blockers':sb}
    if not feedback_path.exists(): return {'report_scope':'abhe_v0_bfcl_dev_feedback_check','schema_path':str(schema_path),'feedback_path':str(feedback_path),'feedback_present':False,'abhe_v0_bfcl_dev_feedback_check_passed':False,'blockers':['dev_feedback_missing']+sb}
    fb=_load(feedback_path); b=sorted(set(sb+validate_feedback(fb)))
    return {'report_scope':'abhe_v0_bfcl_dev_feedback_check','schema_path':str(schema_path),'feedback_path':str(feedback_path),'feedback_present':True,'abhe_v0_bfcl_dev_feedback_check_passed':not b,'blockers':b}

def main(argv: Any=None)->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--schema', type=Path, default=DEFAULT_SCHEMA); ap.add_argument('--feedback', type=Path, default=DEFAULT_FEEDBACK); ap.add_argument('--schema-only', action='store_true'); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args=ap.parse_args(argv)
    try: s=check(schema_only=args.schema_only, schema_path=args.schema, feedback_path=args.feedback)
    except (OSError, ValueError, json.JSONDecodeError) as exc: s={'report_scope':'abhe_v0_bfcl_dev_feedback_check','abhe_v0_bfcl_dev_feedback_check_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(s, sort_keys=True) if args.compact else json.dumps(s, indent=2, sort_keys=True))
    return 1 if args.strict and not s.get('abhe_v0_bfcl_dev_feedback_check_passed') else 0
if __name__=='__main__': raise SystemExit(main())
