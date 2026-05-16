#!/usr/bin/env python3
"""Build a fail-closed ABHE-v0 BFCL fresh dev slice plan."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any, Dict, List, Optional
from scripts.check_abhe_no_leakage_boundary import scan_value
DEFAULT_OUTPUT = Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_plan.json')
DEFAULT_APPROVAL_PACKET = Path('outputs/artifacts/stage1_bfcl_acceptance/abhe_fresh_dev_slice_approval_packet.json')
TARGET_ENTRIES = ['state_tracking_v0', 'hallucination_abstain_v0']

def _load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict): raise ValueError(f'{path} must contain a JSON object')
    return data

def _approval_authorized(path: Path) -> bool:
    if not path.exists(): return False
    try: data = _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError): return False
    return data.get('approval_status') == 'approved' and data.get('authorized') is True

def build_plan(*, bfcl_dataset_path: Optional[Path] = None, approval_packet: Path = DEFAULT_APPROVAL_PACKET) -> Dict[str, Any]:
    dataset_available = bfcl_dataset_path is not None and bfcl_dataset_path.exists()
    approval_authorized = _approval_authorized(approval_packet)
    execution_blockers: List[str] = []
    if not dataset_available: execution_blockers.append('bfcl_dataset_path_missing')
    if not approval_authorized: execution_blockers.append('fresh_dev_slice_approval_missing')
    plan = {
        'artifact_kind': 'abhe_v0_bfcl_fresh_dev_slice_plan', 'schema_version': 'abhe_v0_bfcl_fresh_dev_slice_plan_v0',
        'approval_required': True, 'approval_packet_path': str(approval_packet), 'approval_authorized': approval_authorized,
        'fresh_dev_slice_materialized': False, 'source_dataset': 'BFCL',
        'bfcl_dataset_path_status': 'present' if dataset_available else 'missing',
        'bfcl_dataset_path_hash': hashlib.sha256(str(bfcl_dataset_path).encode('utf-8')).hexdigest() if dataset_available else 'pending_until_dataset_path_reviewed',
        'entry_ids': TARGET_ENTRIES, 'target_case_count_per_entry': '10_to_20',
        'source_160_compact_cases_reused_for_validation': False, 'archive_seed_source_excluded': True,
        'selected_case_ids_hash': 'pending_until_materialized', 'selected_case_ids_hash_immutable_after_materialization': True,
        'raw_material_persisted': False, 'raw_material_absent': True,
        'provider_calls_made': False, 'bfcl_generate_called': False, 'bfcl_evaluate_called': False, 'scorer_called': False,
        'performance_evidence': False, 'holdout_touched': False, 'full_suite_touched': False,
        'execution_blockers': sorted(set(execution_blockers)),
        'next_required_action': 'request_fresh_dev_slice_approval_and_dataset_path_review',
    }
    plan['blockers'] = scan_value(plan, label='abhe_v0_bfcl_fresh_dev_slice_plan')
    plan['abhe_v0_bfcl_fresh_dev_slice_plan_passed'] = not plan['blockers']
    return plan

def write_plan(output: Path, plan: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(plan, indent=2, sort_keys=True)+'\n', encoding='utf-8')

def main(argv: Any = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--bfcl-dataset-path', type=Path); ap.add_argument('--approval-packet', type=Path, default=DEFAULT_APPROVAL_PACKET); ap.add_argument('--output', type=Path, default=DEFAULT_OUTPUT); ap.add_argument('--write', action='store_true'); ap.add_argument('--compact', action='store_true'); ap.add_argument('--strict', action='store_true'); args = ap.parse_args(argv)
    try:
        plan = build_plan(bfcl_dataset_path=args.bfcl_dataset_path, approval_packet=args.approval_packet)
        if args.write: write_plan(args.output, plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        plan = {'report_scope':'abhe_v0_bfcl_fresh_dev_slice_plan','abhe_v0_bfcl_fresh_dev_slice_plan_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(plan, sort_keys=True) if args.compact else json.dumps(plan, indent=2, sort_keys=True))
    return 1 if args.strict and not plan.get('abhe_v0_bfcl_fresh_dev_slice_plan_passed') else 0
if __name__ == '__main__': raise SystemExit(main())
