from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.export_explicit_literal_bfcl_dataset import export_dataset


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_explicit_literal_bfcl_dataset.py"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _row(category: str, index: int = 0, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "id": f"{category}_{index}",
        "question": [[{"role": "user", "content": "Search 'notes.txt'."}]],
        "messages": [{"role": "user", "content": "Search 'notes.txt'."}],
        "function": [{
            "name": "grep",
            "parameters": {
                "type": "object",
                "properties": {"file_name": {"type": "string"}},
                "required": ["file_name"],
            },
        }],
        "extra_metadata": "not exported",
    }
    row.update(overrides)
    return row


def test_export_explicit_literal_bfcl_dataset_from_root_sanitizes_allowed_fields(tmp_path: Path) -> None:
    root = tmp_path / "bfcl_data"
    categories = ["multi_turn_miss_func", "multi_turn_base"]
    for category in categories:
        _write_json(root / f"BFCL_v4_{category}.json", [_row(category)])

    output = tmp_path / "sanitized.json"
    report = export_dataset(output=output, dataset_root=root, categories=categories)

    assert report["dataset_export_passed"] is True
    assert report["exported_record_count"] == 2
    rows = json.loads(output.read_text(encoding="utf-8"))
    assert set(rows[0]) == {"category", "function", "id", "messages", "question"}
    assert rows[0]["category"] == "multi_turn_miss_func"
    assert "extra_metadata" not in rows[0]


def test_export_explicit_literal_bfcl_dataset_rejects_forbidden_gold_field(tmp_path: Path) -> None:
    path = tmp_path / "BFCL_v4_multi_turn_miss_func.json"
    _write_json(path, [_row("multi_turn_miss_func", gold_answer="notes.txt")])

    output = tmp_path / "sanitized.json"
    report = export_dataset(output=output, dataset_files=[path], categories=["multi_turn_miss_func"])

    assert report["dataset_export_passed"] is False
    assert "dataset_export_rejected_records_present" in report["blockers"]
    assert report["exported_record_count"] == 0
    assert report["rejected_records"][0]["forbidden_fields"] == ["gold_answer"]
    assert json.loads(output.read_text(encoding="utf-8")) == []


def test_export_explicit_literal_bfcl_dataset_fails_closed_when_category_file_missing(tmp_path: Path) -> None:
    root = tmp_path / "bfcl_data"
    root.mkdir()
    output = tmp_path / "sanitized.json"

    report = export_dataset(output=output, dataset_root=root, categories=["multi_turn_base"])

    assert report["dataset_export_passed"] is False
    assert "dataset_file_missing:multi_turn_base" in report["blockers"]
    assert "dataset_export_category_coverage_missing" in report["blockers"]


def test_export_explicit_literal_bfcl_dataset_cli_help() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "--dataset-root" in result.stdout
    assert "--dataset-file" in result.stdout
    assert "--output" in result.stdout
