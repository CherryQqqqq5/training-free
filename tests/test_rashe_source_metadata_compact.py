import json
import subprocess
import sys
from pathlib import Path

from scripts import check_rashe_source_metadata_compact as checker


RAW_SECRET = 'raw prompt text must not leak'


def write_metadata_root(root: Path, *, count: int = 20) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for category in checker.APPROVED_CATEGORIES:
        rows = []
        for ordinal in range(count):
            rows.append(
                {
                    'category': category,
                    'ordinal': ordinal,
                    'prompt_family': checker.CATEGORY_PROMPT_FAMILY[category],
                    "source_nonce": "sourceNonce%02d%sABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" % (ordinal, category),
                    'source_family_id': checker.CATEGORY_SOURCE_FAMILY_ID[category],
                }
            )
        (root / f'{category}.jsonl').write_text('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n')


def rewrite_category(root: Path, category: str, rows: list[dict]) -> None:
    (root / f'{category}.jsonl').write_text('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n')


def read_category(root: Path, category: str) -> list[dict]:
    return [json.loads(line) for line in (root / f'{category}.jsonl').read_text().splitlines()]


def test_metadata_root_checker_passes_valid_8x20_fixture(tmp_path):
    root = tmp_path / 'approved_source_metadata_compact'
    write_metadata_root(root)

    summary = checker.check_root(root)

    assert summary['blockers'] == []
    assert sum(summary['category_counts'].values()) == 160
    assert summary['category_counts'] == {category: 20 for category in checker.APPROVED_CATEGORIES}


def test_metadata_root_checker_missing_root_reports_precise_blocker(tmp_path):
    missing_root = tmp_path / 'missing'

    summary = checker.check_root(missing_root)

    assert summary['blockers'] == [f'approved_bfcl_source_metadata_missing:{missing_root}']
    assert summary['category_counts'] == {}


def test_metadata_root_checker_rejects_raw_fields_without_leaking_values(tmp_path):
    for raw_field in [
        'case_id',
        'raw_prompt',
        'gold',
        'expected',
        'reference',
        'scorer_diff',
        'candidate_output',
        'repair_output',
        'feedback',
        'holdout_feedback',
        'full_suite_feedback',
        'raw_trace',
        'provider_payload',
    ]:
        root = tmp_path / raw_field
        write_metadata_root(root)
        rows = read_category(root, 'agentic_web_search')
        rows[0][raw_field] = RAW_SECRET
        rewrite_category(root, 'agentic_web_search', rows)

        blockers = checker.check_root(root)['blockers']

        assert any('source_metadata_forbidden_field' in blocker or 'source_metadata_extra_field' in blocker for blocker in blockers)
        assert all(RAW_SECRET not in blocker for blocker in blockers)


def test_metadata_root_checker_rejects_source_family_id_drift(tmp_path):
    root = tmp_path / 'family_drift'
    write_metadata_root(root)
    rows = read_category(root, 'agentic_web_search')
    rows[0]['source_family_id'] = 'agentic_web_case_0'
    rows[1]['source_family_id'] = 'agentic_memory'
    rewrite_category(root, 'agentic_web_search', rows)

    blockers = checker.check_root(root)['blockers']

    assert any('source_metadata_source_family_id_not_taxonomy' in blocker for blocker in blockers)
    assert any('source_metadata_source_family_id_not_signed' in blocker for blocker in blockers)


def test_metadata_root_checker_rejects_count_ordinal_prompt_family_and_nonce_drift(tmp_path):
    root = tmp_path / 'shape_drift'
    write_metadata_root(root)
    rows = read_category(root, 'agentic_web_search')[:-1]
    rows[0]['ordinal'] = 99
    rows[1]['prompt_family'] = 'raw prompt summary'
    rows[2]['source_nonce'] = 'too-short'
    rewrite_category(root, 'agentic_web_search', rows)

    blockers = checker.check_root(root)['blockers']

    assert any('source_metadata_count_not_signed:agentic_web_search:19' in blocker for blocker in blockers)
    assert any('source_metadata_ordinal_not_continuous:agentic_web_search:99:0' in blocker for blocker in blockers)
    assert any('source_metadata_prompt_family_not_taxonomy' in blocker for blocker in blockers)
    assert any('source_metadata_nonce_format_invalid:agentic_web_search:2' in blocker for blocker in blockers)


def test_metadata_root_checker_cli_strict_passes_fixture(tmp_path):
    root = tmp_path / 'approved_source_metadata_compact'
    write_metadata_root(root)

    result = subprocess.run(
        [sys.executable, 'scripts/check_rashe_source_metadata_compact.py', '--root', str(root), '--compact', '--strict'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary['rashe_source_metadata_compact_passed'] is True
    assert summary['total_records'] == 160
    assert summary['source_family_id_taxonomy'] == sorted(checker.SOURCE_FAMILY_ID_TAXONOMY)


def test_metadata_root_checker_cli_default_root_passes_after_approval():
    result = subprocess.run(
        [sys.executable, 'scripts/check_rashe_source_metadata_compact.py', '--compact', '--strict'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary['rashe_source_metadata_compact_passed'] is True
    assert summary['total_records'] == 160
    assert summary['blockers'] == []
