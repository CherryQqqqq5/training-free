from __future__ import annotations

import json
from pathlib import Path

from scripts.check_explicit_literal_candidate_pool import evaluate


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _candidate(case_id: str, **overrides) -> dict:
    row = {
        "case_id": case_id,
        "category": "multi_turn_miss_func",
        "candidate_generatable": True,
        "candidate_origin": "theory_prior_explicit_literal_from_source_result_context",
        "candidate_rules_type": "explicit_required_arg_literal_completion",
        "rule_type": "explicit_required_arg_literal_completion",
        "source_run_root": "outputs/source",
        "tool": "grep",
        "schema_arg_name": "file_name",
        "selected_literal": f"{case_id}.txt",
        "literal_source": "current_request",
        "literal_source_span": f"{case_id}.txt",
        "literal_source_text_hash": f"hash-{case_id}",
        "used_gold_fields": False,
        "used_score_fields": False,
        "used_candidate_output": False,
        "retention_prior": {"retain_eligibility": "demote_candidate"},
    }
    row.update(overrides)
    return row


def _write_manifests(root: Path, *, dev_ids: list[str] | None = None, holdout_ids: list[str] | None = None) -> tuple[Path, Path]:
    dev = root / "dev.json"
    holdout = root / "holdout.json"
    _write_json(dev, {
        "selected_case_ids": dev_ids if dev_ids is not None else [f"case_{i}" for i in range(20)],
        "planned_commands": [],
        "candidate_commands": [],
    })
    _write_json(holdout, {
        "selected_case_ids": holdout_ids if holdout_ids is not None else [f"case_{i}" for i in range(20, 40)],
        "planned_commands": [],
        "candidate_commands": [],
    })
    return dev, holdout


def test_explicit_literal_candidate_pool_happy_path(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    _write_jsonl(candidates, [_candidate(f"case_{i}") for i in range(40)])
    dev, holdout = _write_manifests(tmp_path)

    report = evaluate(candidates, dev, holdout)

    assert report["explicit_literal_candidate_pool_passed"] is True
    assert report["eligible_count"] == 40
    assert report["blockers"] == []


def test_explicit_literal_candidate_pool_blocks_below_35(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    _write_jsonl(candidates, [_candidate(f"case_{i}") for i in range(34)])
    dev, holdout = _write_manifests(tmp_path)

    report = evaluate(candidates, dev, holdout)

    assert report["explicit_literal_candidate_pool_passed"] is False
    assert "eligible_explicit_literal_candidates_below_35" in report["blockers"]


def test_explicit_literal_candidate_pool_blocks_gold_leakage(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    rows = [_candidate(f"case_{i}") for i in range(40)]
    rows[0]["literal_source_span"] = "gold_answer"
    _write_jsonl(candidates, rows)
    dev, holdout = _write_manifests(tmp_path)

    report = evaluate(candidates, dev, holdout)

    assert report["explicit_literal_candidate_pool_passed"] is False
    assert "candidate_gold_leakage_detected" in report["blockers"]


def test_explicit_literal_candidate_pool_blocks_duplicate_case(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    rows = [_candidate(f"case_{i}") for i in range(39)]
    rows.append(_candidate("case_0"))
    _write_jsonl(candidates, rows)
    dev, holdout = _write_manifests(tmp_path)

    report = evaluate(candidates, dev, holdout)

    assert report["explicit_literal_candidate_pool_passed"] is False
    assert "candidate_duplicate_case_ids_present" in report["blockers"]
    assert report["duplicate_candidate_case_ids"] == ["case_0"]


def test_explicit_literal_candidate_pool_blocks_dev_holdout_overlap(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    _write_jsonl(candidates, [_candidate(f"case_{i}") for i in range(40)])
    dev, holdout = _write_manifests(
        tmp_path,
        dev_ids=[f"case_{i}" for i in range(20)],
        holdout_ids=["case_0", *[f"case_{i}" for i in range(21, 40)]],
    )

    report = evaluate(candidates, dev, holdout)

    assert report["explicit_literal_candidate_pool_passed"] is False
    assert "dev_holdout_overlap_present" in report["blockers"]
    assert report["dev_holdout_overlap_case_ids"] == ["case_0"]


def test_explicit_literal_candidate_pool_blocks_bad_literal_source(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.jsonl"
    rows = [_candidate(f"case_{i}") for i in range(40)]
    rows[0]["literal_source"] = "source_result_only"
    _write_jsonl(candidates, rows)
    dev, holdout = _write_manifests(tmp_path)

    report = evaluate(candidates, dev, holdout)

    assert report["explicit_literal_candidate_pool_passed"] is False
    assert "candidate_literal_source_not_current_context" in report["blockers"]
    assert "source_result_only_candidates_are_diagnostic_only" in report["blockers"]
