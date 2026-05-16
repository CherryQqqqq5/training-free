#!/usr/bin/env python3
"""Run or dry-run the ABHE-v0 paired BFCL dev smoke gate."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from typing import Any, Dict
from scripts.check_abhe_v0_bfcl_execution_readiness import build_report
DEFAULT_MANIFEST=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_dry_run_manifest.json')
DEFAULT_RESULT=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_result.json')
DEFAULT_APPROVAL_PACKET=Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_packet.json')

def build_dry_run_manifest(arm: str)->Dict[str,Any]:
    return {'artifact_kind':'abhe_v0_bfcl_dev_smoke_dry_run_manifest','schema_version':'abhe_v0_bfcl_dev_smoke_dry_run_manifest_v0','arm':arm,'dry_run':True,'compact_only':True,'provider_calls_made':False,'bfcl_generate_called':False,'bfcl_evaluate_called':False,'scorer_called':False,'candidate_generated':False,'candidate_jsonl_created':False,'performance_evidence':False,'result_path_reserved':str(DEFAULT_RESULT),'execution_started':False,'next_required_action':'provide_approved_execution_packet_before_real_bfcl_dev_smoke'}

def write_json(path: Path, data: Dict[str,Any])->None:
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data, indent=2, sort_keys=True)+'\n', encoding='utf-8')

def main(argv: Any=None)->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--arm', choices=['baseline','candidate'], required=True); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--execute-approved', action='store_true'); ap.add_argument('--approval-packet', type=Path, default=DEFAULT_APPROVAL_PACKET); ap.add_argument('--manifest-output', type=Path, default=DEFAULT_MANIFEST); ap.add_argument('--compact-only', action='store_true'); args=ap.parse_args(argv)
    if args.execute_approved:
        readiness=build_report(args.approval_packet)
        if readiness.get('abhe_v0_bfcl_execution_ready') is not True:
            print(json.dumps({'report_scope':'abhe_v0_bfcl_dev_smoke_execute_gate','execution_started':False,'provider_calls_made':False,'bfcl_generate_called':False,'bfcl_evaluate_called':False,'scorer_called':False,'blockers':readiness.get('blockers', [])}, sort_keys=True)); return 2
        print(json.dumps({'report_scope':'abhe_v0_bfcl_dev_smoke_execute_gate','execution_started':False,'blockers':['real_execution_not_implemented_in_gate_commit']}, sort_keys=True)); return 2
    if not args.dry_run:
        print(json.dumps({'report_scope':'abhe_v0_bfcl_dev_smoke_runner','execution_started':False,'blockers':['dry_run_required_without_execute_approved']}, sort_keys=True)); return 2
    m=build_dry_run_manifest(args.arm); write_json(args.manifest_output, m); print(json.dumps(m, sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
