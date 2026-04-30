from __future__ import annotations

import json
from pathlib import Path

from scripts.check_explicit_literal_dataset import DEFAULT_PRIORITY_CATEGORIES, evaluate


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _record(category: str, index: int = 0, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": f"{category}_{index}",
        "category": category,
        "question": [[{"role": "user", "content": "Search 'notes.txt'."}]],
        "function": [{
            "name": "grep",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "file_name": {"type": "string"},
                },
                "required": ["pattern", "file_name"],
            },
        }],
    }
    row.update(overrides)
    return row


def test_explicit_literal_dataset_gate_happy_path_priority_coverage(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [_record(category) for category in DEFAULT_PRIORITY_CATEGORIES])

    report = evaluate(dataset)

    assert report["explicit_literal_dataset_gate_passed"] is True
    assert report["blockers"] == []
    assert report["gold_score_candidate_fields_required_or_read"] is False
    assert all(report["category_counts"][category] == 1 for category in DEFAULT_PRIORITY_CATEGORIES)


def test_explicit_literal_dataset_gate_blocks_missing_schema_parts(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "multi_turn_miss_func_0",
        "category": "multi_turn_miss_func",
        "messages": [{"role": "user", "content": "Search 'notes.txt'."}],
        "function": [{"name": "grep", "parameters": {"type": "object", "properties": {}}}],
    }])

    report = evaluate(dataset, ["multi_turn_miss_func"])

    assert report["explicit_literal_dataset_gate_passed"] is False
    assert "dataset_records_malformed" in report["blockers"]
    assert report["malformed_records"][0]["errors"] == ["required_args_missing"]


def test_explicit_literal_dataset_gate_blocks_forbidden_gold_score_candidate_fields(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    row = _record("multi_turn_miss_func", gold_answer="notes.txt")
    _write_json(dataset, [row])

    report = evaluate(dataset, ["multi_turn_miss_func"])

    assert report["explicit_literal_dataset_gate_passed"] is False
    assert "dataset_forbidden_fields_present" in report["blockers"]
    assert report["forbidden_records"] == [{"case_id": "multi_turn_miss_func_0", "fields": ["gold_answer"]}]


def test_explicit_literal_dataset_gate_blocks_missing_priority_category(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [_record("multi_turn_miss_func")])

    report = evaluate(dataset)

    assert report["explicit_literal_dataset_gate_passed"] is False
    assert "priority_category_coverage_missing" in report["blockers"]
    assert "multi_turn_base" in report["missing_categories"]


def test_explicit_literal_dataset_gate_blocks_duplicate_ids(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [_record("multi_turn_miss_func"), _record("multi_turn_miss_func")])

    report = evaluate(dataset, ["multi_turn_miss_func"])

    assert report["explicit_literal_dataset_gate_passed"] is False
    assert "dataset_duplicate_ids_present" in report["blockers"]
    assert report["duplicate_ids"] == ["multi_turn_miss_func_0"]



def test_explicit_literal_dataset_gate_accepts_no_arg_function_schema(tmp_path: Path) -> None:
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "multi_turn_miss_func_0",
        "category": "multi_turn_miss_func",
        "messages": [{"role": "user", "content": "Check status."}],
        "function": [{
            "name": "VehicleControlAPI.check_tire_pressure",
            "parameters": {"type": "dict", "properties": {}, "required": []},
        }],
    }])

    report = evaluate(dataset, ["multi_turn_miss_func"])

    assert report["explicit_literal_dataset_gate_passed"] is True
    assert report["blockers"] == []
