from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.check_wrong_arg_key_alias_repair_diagnostic import build_report

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_wrong_arg_key_alias_repair_diagnostic.py"


def _write_json(path: Path, payload) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path, *, args: dict, dataset_extra: dict | None = None, schema_type: str = "string") -> tuple[Path, Path, Path]:
    category = "multi_turn_miss_func"
    source_root = tmp_path / "source" / category / "baseline"
    result_path = source_root / "bfcl" / "result" / "model" / "multi_turn" / f"BFCL_v4_{category}_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({"id": "case_1", "result": [{"grep": args}]}) + "\n", encoding="utf-8")
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": category, "existing_source_roots": [str(source_root)]}]})
    dataset_row = {
        "id": "case_1",
        "question": [[{"role": "user", "content": "Search a file."}]],
        "function": [{
            "name": "grep",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_name": {"type": schema_type},
                    "pattern": {"type": "string"},
                },
                "required": ["file_name", "pattern"],
            },
        }],
    }
    if dataset_extra:
        dataset_row.update(dataset_extra)
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [dataset_row])
    return source_manifest, dataset, source_root


def test_wrong_arg_key_alias_repair_help() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--help"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0
    assert "--dataset-json" in result.stdout
    assert "--source-manifest" in result.stdout
    assert "--markdown-output" in result.stdout
    assert "--strict" in result.stdout


def test_wrong_arg_key_alias_repair_accepts_deterministic_alias(tmp_path: Path) -> None:
    source_manifest, dataset, _source_root = _fixture(
        tmp_path,
        args={"fileName": "notes.txt", "pattern": "urgent"},
    )
    out_json = tmp_path / "diagnostic.json"
    out_md = tmp_path / "diagnostic.md"

    report = build_report(
        dataset_json=dataset,
        source_manifest=source_manifest,
        categories="multi_turn_miss_func",
        output_json=out_json,
        markdown_output=out_md,
    )

    assert report["wrong_arg_key_alias_repair_diagnostic_passed"] is True
    assert report["diagnostic_only"] is True
    assert report["candidate_pool_authorized"] is False
    assert report["scorer_authorized"] is False
    assert report["performance_evidence"] is False
    counters = report["counters"]
    assert counters["selected_call_count"] == 1
    assert counters["selected_calls_with_function_schema"] == 1
    assert counters["selected_calls_with_required_args"] == 1
    assert counters["required_arg_absent_by_canonical_key_count"] == 1
    assert counters["emitted_alias_key_present_count"] == 1
    assert counters["alias_map_unique_count"] == 1
    assert counters["alias_value_schema_compatible_count"] == 1
    assert counters["wrong_key_alias_candidate_count"] == 1
    assert counters["alias_repair_eligible_count"] == 1
    row = report["eligible_alias_records"][0]
    assert row["source_value_provenance"] == "baseline_emitted_args"
    assert row["canonical_arg"] == "file_name"
    assert row["emitted_alias_key"] == "fileName"
    assert row["tool_choice_mutation"] is False
    assert row["trajectory_mutation"] is False
    assert not (tmp_path / "candidate_rules.jsonl").exists()


def test_wrong_arg_key_alias_repair_rejects_forbidden_gold_field(tmp_path: Path) -> None:
    source_manifest, dataset, _source_root = _fixture(
        tmp_path,
        args={"fileName": "notes.txt", "pattern": "urgent"},
        dataset_extra={"possible_answer": "notes.txt"},
    )

    report = build_report(
        dataset_json=dataset,
        source_manifest=source_manifest,
        categories="multi_turn_miss_func",
        output_json=tmp_path / "diagnostic.json",
        markdown_output=tmp_path / "diagnostic.md",
    )

    assert report["wrong_arg_key_alias_repair_diagnostic_passed"] is False
    assert report["eligible_alias_record_count"] == 0
    assert report["counters"]["reject_reason_counts"]["forbidden_leakage_field_present"] == 1
    assert "wrong_arg_key_alias_repair_eligible_count_zero" in report["blockers"]


def test_wrong_arg_key_alias_repair_rejects_type_mismatch_fail_closed(tmp_path: Path) -> None:
    source_manifest, dataset, _source_root = _fixture(
        tmp_path,
        args={"fileName": "notes.txt", "pattern": "urgent"},
        schema_type="integer",
    )

    report = build_report(
        dataset_json=dataset,
        source_manifest=source_manifest,
        categories="multi_turn_miss_func",
        output_json=tmp_path / "diagnostic.json",
        markdown_output=tmp_path / "diagnostic.md",
    )

    counters = report["counters"]
    assert report["wrong_arg_key_alias_repair_diagnostic_passed"] is False
    assert counters["emitted_alias_key_present_count"] == 1
    assert counters["alias_map_unique_count"] == 1
    assert counters["alias_type_mismatch_count"] == 1
    assert counters["alias_repair_eligible_count"] == 0
    assert counters["reject_reason_counts"]["alias_type_mismatch"] == 1
    assert report["next_recommended_diagnostic"] == "deterministic_schema_local_non_live_repair"
