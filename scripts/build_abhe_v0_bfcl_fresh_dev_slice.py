#!/usr/bin/env python3
"""Build a fail-closed ABHE-v0 BFCL fresh dev slice plan and compact proposal."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from scripts.check_abhe_no_leakage_boundary import scan_value

ARTIFACT_ROOT = Path('outputs/artifacts/stage1_bfcl_acceptance')
DEFAULT_OUTPUT = ARTIFACT_ROOT / 'abhe_v0_bfcl_fresh_dev_slice_plan.json'
DEFAULT_APPROVAL_PACKET = ARTIFACT_ROOT / 'abhe_fresh_dev_slice_approval_packet.json'
DEFAULT_DATASET_SELECTION = ARTIFACT_ROOT / 'abhe_v0_bfcl_dataset_path_selection.json'
DEFAULT_DATASET_REVIEW = ARTIFACT_ROOT / 'abhe_v0_bfcl_dataset_path_review.json'
DEFAULT_CATEGORY_REVIEW = ARTIFACT_ROOT / 'abhe_v0_bfcl_category_review.json'
DEFAULT_SLICE_REVIEW = ARTIFACT_ROOT / 'abhe_v0_bfcl_fresh_dev_slice_review.json'
DEFAULT_EXCLUSION_PROOF = ARTIFACT_ROOT / 'abhe_v0_bfcl_source_exclusion_proof.json'
DEFAULT_SELECTED_DATASET_PATH = Path('.venv/lib/python3.10/site-packages/bfcl_eval/data')
DISCOVERY_ROOT = ARTIFACT_ROOT / 'rashe_source_inputs_compact'
TARGET_ENTRIES = ['state_tracking_v0', 'hallucination_abstain_v0']
APPROVED_STRATA = {
    'state_tracking_v0': ['multi_turn_base', 'multi_turn_long_context', 'multi_turn_miss_func', 'multi_turn_miss_param'],
    'hallucination_abstain_v0': ['irrelevance', 'live_irrelevance', 'live_relevance'],
}
APPROVED_CASE_COUNT = {'state_tracking_v0': 10, 'hallucination_abstain_v0': 10}
HASH_PREFIX = 'sha256:'


def _hash_bytes(data: bytes) -> str:
    return HASH_PREFIX + hashlib.sha256(data).hexdigest()


def _hash_text(text: str) -> str:
    return _hash_bytes(text.encode('utf-8'))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError(f'{path} must contain a JSON object')
    return data


def _approval_authorized(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return data.get('approval_status') == 'approved' and data.get('authorized') is True


def _selected_dataset_path(arg_path: Optional[Path]) -> Path:
    if arg_path is not None:
        return arg_path
    if DEFAULT_DATASET_SELECTION.exists():
        data = _load_json(DEFAULT_DATASET_SELECTION)
        selected = data.get('selected_dataset_path')
        if isinstance(selected, str) and selected and not selected.startswith('pending'):
            return Path(selected)
    return DEFAULT_SELECTED_DATASET_PATH


def _category_file(dataset_path: Path, category: str) -> Path:
    return dataset_path / f'BFCL_v4_{category}.json'


def _iter_json_rows(path: Path) -> List[Tuple[int, Any]]:
    text = path.read_text(encoding='utf-8')
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        rows: List[Tuple[int, Any]] = []
        for idx, line in enumerate(text.splitlines()):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f'{path} is not parseable as JSON or JSONL at row {idx}') from exc
            rows.append((idx, row))
        return rows
    if isinstance(parsed, list):
        return list(enumerate(parsed))
    if isinstance(parsed, dict):
        for key in ('data', 'cases', 'test_cases', 'examples'):
            value = parsed.get(key)
            if isinstance(value, list):
                return list(enumerate(value))
        if all(isinstance(v, dict) for v in parsed.values()):
            return list(enumerate(parsed.values()))
    raise ValueError(f'{path} has unsupported BFCL data structure')


def _source_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return HASH_PREFIX + h.hexdigest()


def _stable_id_hash(row: Any) -> Optional[str]:
    if not isinstance(row, dict):
        return None
    for key in ('id', 'case_id', 'question_id', 'test_case_id', 'uid', 'name'):
        if key in row:
            return _hash_text(str(row[key]))
    return None


def _compact_case(entry_id: str, category: str, source_hash: str, row_index: int, row: Any) -> Dict[str, str]:
    item = {
        'entry_id': entry_id,
        'bfcl_category': category,
        'source_file_hash': source_hash,
        'case_stable_hash': _hash_text(_canonical_json(row)),
        'case_row_index_hash': _hash_text(f'{category}|{row_index}'),
    }
    sid = _stable_id_hash(row)
    if sid:
        item['case_identifier_hash'] = sid
    return item


def _archive_seed_categories() -> set:
    if not DISCOVERY_ROOT.exists():
        return set()
    return {path.stem for path in DISCOVERY_ROOT.glob('*.jsonl')}


def _select_round_robin(dataset_path: Path, default_seed_start_row_index: int = 20) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    selected: List[Dict[str, str]] = []
    seed_categories = _archive_seed_categories()
    summary: Dict[str, Any] = {'category_counts': {}, 'selection_start_row_index_by_category': {}, 'selection_strategy': 'round_robin_across_approved_strata_with_seed_category_window_exclusion'}
    for entry_id in TARGET_ENTRIES:
        by_category: Dict[str, List[Dict[str, str]]] = {}
        for category in APPROVED_STRATA[entry_id]:
            path = _category_file(dataset_path, category)
            if not path.exists():
                raise FileNotFoundError(f'approved BFCL category file missing: {path}')
            rows = _iter_json_rows(path)
            source_hash = _source_file_hash(path)
            start_row_index = default_seed_start_row_index if category in seed_categories else 0
            eligible = [_compact_case(entry_id, category, source_hash, row_idx, row) for row_idx, row in rows if row_idx >= start_row_index]
            by_category[category] = eligible
            summary['selection_start_row_index_by_category'][category] = start_row_index
            summary['category_counts'][category] = {'total_rows': len(rows), 'eligible_rows_after_seed_window': len(eligible), 'source_file_hash': source_hash}
        picked: List[Dict[str, str]] = []
        cursors = {category: 0 for category in APPROVED_STRATA[entry_id]}
        while len(picked) < APPROVED_CASE_COUNT[entry_id]:
            progressed = False
            for category in APPROVED_STRATA[entry_id]:
                pos = cursors[category]
                if pos < len(by_category[category]):
                    picked.append(by_category[category][pos])
                    cursors[category] = pos + 1
                    progressed = True
                    if len(picked) == APPROVED_CASE_COUNT[entry_id]:
                        break
            if not progressed:
                raise ValueError(f'insufficient eligible BFCL cases for {entry_id}')
        selected.extend(picked)
        summary[f'{entry_id}_selected_count'] = len(picked)
    return selected, summary


def selected_case_ids_hash(compact_cases: Iterable[Dict[str, str]]) -> str:
    keys = []
    for item in compact_cases:
        keys.append('|'.join([item['entry_id'], item['bfcl_category'], item['source_file_hash'], item['case_stable_hash'], item['case_row_index_hash']]))
    return _hash_text('\n'.join(sorted(keys)))


def _discovery_hashes() -> Tuple[set, int, Dict[str, int]]:
    hashes = set()
    count = 0
    by_file: Dict[str, int] = {}
    if not DISCOVERY_ROOT.exists():
        raise FileNotFoundError(f'discovery compact source root missing: {DISCOVERY_ROOT}')
    for path in sorted(DISCOVERY_ROOT.glob('*.jsonl')):
        file_count = 0
        category = path.stem
        with path.open(encoding='utf-8') as fh:
            for row_idx, line in enumerate(fh):
                if not line.strip():
                    continue
                file_count += 1
                count += 1
                hashes.add(_hash_text(line.strip()))
                hashes.add(_hash_text(f'{category}|{row_idx}'))
        by_file[path.name] = file_count
    return hashes, count, by_file


def build_review_artifacts(dataset_path: Path) -> Dict[str, Any]:
    if not dataset_path.exists():
        return {'status': 'blocked', 'blockers': ['bfcl_dataset_path_missing'], 'dataset_path': str(dataset_path)}
    compact_cases, selection_summary = _select_round_robin(dataset_path)
    proposed_hash = selected_case_ids_hash(compact_cases)
    discovery_hashes, discovery_count, discovery_by_file = _discovery_hashes()
    candidate_hashes = set()
    for item in compact_cases:
        candidate_hashes.add(item['case_stable_hash'])
        candidate_hashes.add(item['case_row_index_hash'])
    overlaps = sorted(discovery_hashes.intersection(candidate_hashes))
    return {
        'status': 'complete' if not overlaps else 'blocked',
        'blockers': [] if not overlaps else ['archive_seed_overlap_detected'],
        'dataset_path': str(dataset_path),
        'compact_cases': compact_cases,
        'selection_summary': selection_summary,
        'proposed_selected_case_ids_hash': proposed_hash,
        'discovery_source_hash_count': discovery_count,
        'discovery_source_file_counts': discovery_by_file,
        'candidate_case_hash_count': len(compact_cases),
        'overlap_hashes': overlaps,
        'overlap_count': len(overlaps),
    }


def write_review_artifacts(result: Dict[str, Any]) -> None:
    dataset_path = result['dataset_path']
    selection = {
        'artifact_kind': 'abhe_v0_bfcl_dataset_path_selection',
        'schema_version': 'abhe_v0_bfcl_dataset_path_selection_v0',
        'selected_dataset_path': dataset_path,
        'authorized_for': 'fresh_slice_hash_and_overlap_proof_only',
        'authorized': False,
        'fresh_dev_slice_materialization_authorized': False,
        'bfcl_generate_authorized': False,
        'bfcl_evaluate_authorized': False,
        'scorer_authorized': False,
        'candidate_generation_authorized': False,
        'performance_evidence': False,
        'approved_strata': APPROVED_STRATA,
        'approved_case_count_per_entry': APPROVED_CASE_COUNT,
        'raw_material_committed': False,
        'next_required_action': 'review_proposed_case_hash_and_overlap_proof',
    }
    dataset_review = _load_json(DEFAULT_DATASET_REVIEW)
    dataset_review.update({'selected_dataset_path': dataset_path, 'selection_artifact': str(DEFAULT_DATASET_SELECTION), 'selected_for': 'fresh_slice_hash_and_overlap_proof_only', 'authorized': False, 'raw_material_committed': False, 'next_required_action': 'review_proposed_case_hash_and_overlap_proof'})
    category_review = _load_json(DEFAULT_CATEGORY_REVIEW)
    category_review.update({'selected_dataset_path': dataset_path, 'category_or_file_count_summary': result.get('selection_summary', {}).get('category_counts', {}), 'authorized': False, 'raw_material_persisted': False})
    slice_review = _load_json(DEFAULT_SLICE_REVIEW)
    if result['status'] == 'complete':
        cases = result['compact_cases']
        slice_review.update({
            'selected_dataset_path': dataset_path,
            'selected_case_count_per_entry_proposed': 10,
            'proposed_selected_case_ids_hash': result['proposed_selected_case_ids_hash'],
            'case_keys_persisted': True,
            'proposed_compact_case_identifiers': cases,
            'case_count_by_entry': {entry: sum(1 for item in cases if item['entry_id'] == entry) for entry in TARGET_ENTRIES},
            'case_count_by_category': {cat: sum(1 for item in cases if item['bfcl_category'] == cat) for cats in APPROVED_STRATA.values() for cat in cats},
            'fresh_dev_slice_materialized': False,
            'authorized': False,
            'raw_cases_persisted': False,
            'gold_expected_persisted': False,
            'scorer_diff_persisted': False,
            'performance_evidence': False,
            'next_required_action': 'review_proposed_case_ids_hash_before_materialization_approval',
        })
    proof = {
        'artifact_kind': 'abhe_v0_bfcl_source_exclusion_proof',
        'schema_version': 'abhe_v0_bfcl_source_exclusion_proof_v0',
        'overlap_check_status': result['status'],
        'blockers': result['blockers'],
        'discovery_source_hash_count': result.get('discovery_source_hash_count', 0),
        'candidate_case_hash_count': result.get('candidate_case_hash_count', 0),
        'overlap_count': result.get('overlap_count'),
        'overlap_hashes': result.get('overlap_hashes', []),
        'source_160_compact_cases_reused_for_validation': False,
        'archive_seed_source_excluded': result.get('overlap_count') == 0,
        'hash_rule_description': 'Discovery compact rows are compared with proposed BFCL compact case hashes and category row-window hashes; only compact hashes are persisted.',
        'discovery_source_file_counts': result.get('discovery_source_file_counts', {}),
        'candidate_case_hash_rule': 'sha256 over compact case key fields plus row-window fallback hash; raw BFCL case content is not persisted.',
        'raw_material_persisted': False,
        'performance_evidence': False,
        'next_required_action': 'review_overlap_count_before_fresh_slice_materialization_approval',
    }
    for path, data in [(DEFAULT_DATASET_SELECTION, selection), (DEFAULT_DATASET_REVIEW, dataset_review), (DEFAULT_CATEGORY_REVIEW, category_review), (DEFAULT_SLICE_REVIEW, slice_review), (DEFAULT_EXCLUSION_PROOF, proof)]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def build_plan(*, bfcl_dataset_path: Optional[Path] = None, approval_packet: Path = DEFAULT_APPROVAL_PACKET) -> Dict[str, Any]:
    selected_path = _selected_dataset_path(bfcl_dataset_path)
    dataset_available = selected_path.exists()
    approval_authorized = _approval_authorized(approval_packet)
    execution_blockers: List[str] = []
    if not dataset_available:
        execution_blockers.append('bfcl_dataset_path_missing')
    if not approval_authorized:
        execution_blockers.append('fresh_dev_slice_approval_missing')
    selected_hash = 'pending_until_reviewer_selects_dataset_path'
    proof_status = 'pending_until_review_artifacts_built'
    if DEFAULT_SLICE_REVIEW.exists():
        try:
            selected_hash = _load_json(DEFAULT_SLICE_REVIEW).get('proposed_selected_case_ids_hash', selected_hash)
        except Exception:
            pass
    if DEFAULT_EXCLUSION_PROOF.exists():
        try:
            proof_status = _load_json(DEFAULT_EXCLUSION_PROOF).get('overlap_check_status', proof_status)
        except Exception:
            pass
    plan = {
        'artifact_kind': 'abhe_v0_bfcl_fresh_dev_slice_plan',
        'schema_version': 'abhe_v0_bfcl_fresh_dev_slice_plan_v0',
        'approval_required': True,
        'approval_packet_path': str(approval_packet),
        'approval_authorized': approval_authorized,
        'fresh_dev_slice_materialized': False,
        'source_dataset': 'BFCL',
        'selected_dataset_path': str(selected_path),
        'bfcl_dataset_path_status': 'present' if dataset_available else 'missing',
        'bfcl_dataset_path_hash': _hash_text(str(selected_path)) if dataset_available else 'pending_until_dataset_path_reviewed',
        'entry_ids': TARGET_ENTRIES,
        'approved_strata': APPROVED_STRATA,
        'target_case_count_per_entry': '10_to_20',
        'proposed_case_count_per_entry': APPROVED_CASE_COUNT,
        'source_160_compact_cases_reused_for_validation': False,
        'archive_seed_source_excluded': True,
        'selected_case_ids_hash': 'pending_until_materialized',
        'proposed_selected_case_ids_hash': selected_hash,
        'source_exclusion_proof_status': proof_status,
        'selected_case_ids_hash_immutable_after_materialization': True,
        'raw_material_persisted': False,
        'raw_material_absent': True,
        'provider_calls_made': False,
        'bfcl_generate_called': False,
        'bfcl_evaluate_called': False,
        'scorer_called': False,
        'performance_evidence': False,
        'holdout_touched': False,
        'full_suite_touched': False,
        'execution_blockers': sorted(set(execution_blockers)),
        'next_required_action': 'request_fresh_dev_slice_materialization_approval_after_hash_review',
    }
    plan['blockers'] = scan_value(plan, label='abhe_v0_bfcl_fresh_dev_slice_plan')
    plan['abhe_v0_bfcl_fresh_dev_slice_plan_passed'] = not plan['blockers']
    return plan


def write_plan(output: Path, plan: Dict[str, Any]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(plan, indent=2, sort_keys=True)+'\n', encoding='utf-8')


def main(argv: Any = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bfcl-dataset-path', type=Path)
    ap.add_argument('--approval-packet', type=Path, default=DEFAULT_APPROVAL_PACKET)
    ap.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument('--write', action='store_true')
    ap.add_argument('--write-review-artifacts', action='store_true')
    ap.add_argument('--compact', action='store_true')
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args(argv)
    try:
        selected_path = _selected_dataset_path(args.bfcl_dataset_path)
        review_result = None
        if args.write_review_artifacts:
            review_result = build_review_artifacts(selected_path)
            write_review_artifacts(review_result)
        plan = build_plan(bfcl_dataset_path=selected_path, approval_packet=args.approval_packet)
        if review_result is not None:
            plan['review_artifact_build_status'] = review_result['status']
            plan['review_artifact_build_blockers'] = review_result['blockers']
        if args.write:
            write_plan(args.output, plan)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        plan = {'report_scope':'abhe_v0_bfcl_fresh_dev_slice_plan','abhe_v0_bfcl_fresh_dev_slice_plan_passed':False,'blockers':[f'load_failed:{exc}']}
    print(json.dumps(plan, sort_keys=True) if args.compact else json.dumps(plan, indent=2, sort_keys=True))
    return 1 if args.strict and not plan.get('abhe_v0_bfcl_fresh_dev_slice_plan_passed') else 0

if __name__ == '__main__':
    raise SystemExit(main())
