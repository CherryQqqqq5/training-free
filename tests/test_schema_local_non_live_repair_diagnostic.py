from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.check_schema_local_non_live_repair_diagnostic import build_report

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_schema_local_non_live_repair_diagnostic.py"


def _write_json(path: Path, payload) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _run_fixture(tmp_path: Path, *, arg_schema: dict, value, dataset_extra: dict | None = None) -> dict:
    category = "multi_turn_miss_func"
    source_root = tmp_path / "source" / category / "baseline"
    result_path = source_root / "bfcl" / "result" / "model" / "multi_turn" / f"BFCL_v4_{category}_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({"id": "case_1", "result": [{"tool": {"target": value}}]}) + "\n", encoding="utf-8")
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": category, "existing_source_roots": [str(source_root)]}]})
    dataset_row = {
        "id": "case_1",
        "question": [[{"role": "user", "content": "Use the tool."}]],
        "function": [{
            "name": "tool",
            "parameters": {
                "type": "object",
                "properties": {"target": arg_schema},
                "required": ["target"],
            },
        }],
    }
    if dataset_extra:
        dataset_row.update(dataset_extra)
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [dataset_row])
    return build_report(
        dataset_json=dataset,
        source_manifest=source_manifest,
        categories=category,
        output_json=tmp_path / "diagnostic.json",
        markdown_output=tmp_path / "diagnostic.md",
    )


def test_schema_local_non_live_help() -> None:
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


def test_schema_local_accepts_numeric_string_to_integer(tmp_path: Path) -> None:
    report = _run_fixture(tmp_path, arg_schema={"type": "integer"}, value="42")
    counters = report["counters"]
    assert report["schema_local_non_live_repair_diagnostic_passed"] is True
    assert report["diagnostic_only"] is True
    assert report["candidate_pool_authorized"] is False
    assert counters["selected_call_count"] == 1
    assert counters["selected_calls_with_function_schema"] == 1
    assert counters["selected_calls_with_required_args"] == 1
    assert counters["required_args_present_count"] == 1
    assert counters["schema_local_checked_arg_count"] == 1
    assert counters["schema_local_type_mismatch_count"] == 1
    assert counters["numeric_string_to_integer_candidate_count"] == 1
    assert counters["schema_local_repair_eligible_count"] == 1
    row = report["eligible_schema_local_records"][0]
    assert row["value_provenance"] == "baseline_emitted_args"
    assert row["schema_provenance"] == "dataset_tool_schema"
    assert row["conversion"] == "numeric_string_to_integer"
    assert row["tool_choice_mutation"] is False
    assert row["trajectory_mutation"] is False
    assert row["unrelated_arg_mutation"] is False


def test_schema_local_accepts_number_boolean_enum_and_array_patterns(tmp_path: Path) -> None:
    cases = [
        ({"type": "number"}, "3.14", "numeric_string_to_number_candidate_count"),
        ({"type": "boolean"}, "false", "boolean_string_candidate_count"),
        ({"type": "string", "enum": ["Red", "Blue"]}, "red", "enum_case_normalization_candidate_count"),
        ({"type": "array", "items": {"type": "string"}}, "tag", "singleton_array_wrap_candidate_count"),
    ]
    for idx, (schema, value, counter) in enumerate(cases):
        report = _run_fixture(tmp_path / str(idx), arg_schema=schema, value=value)
        assert report["schema_local_non_live_repair_diagnostic_passed"] is True
        assert report["counters"][counter] == 1
        assert report["counters"]["schema_local_repair_eligible_count"] == 1


def test_schema_local_rejects_noop_already_valid(tmp_path: Path) -> None:
    report = _run_fixture(tmp_path, arg_schema={"type": "integer"}, value=42)
    counters = report["counters"]
    assert report["schema_local_non_live_repair_diagnostic_passed"] is False
    assert counters["schema_local_noop_already_valid_count"] == 1
    assert counters["schema_local_repair_eligible_count"] == 0
    assert counters["reject_reason_counts"]["schema_local_noop_already_valid"] == 1
    assert report["next_recommended_action"] == "research_review_required_do_not_lower_standards"


def test_schema_local_rejects_forbidden_dataset_field(tmp_path: Path) -> None:
    report = _run_fixture(
        tmp_path,
        arg_schema={"type": "integer"},
        value="42",
        dataset_extra={"possible_answer": 42},
    )
    assert report["schema_local_non_live_repair_diagnostic_passed"] is False
    assert report["eligible_schema_local_record_count"] == 0
    assert report["counters"]["reject_reason_counts"]["forbidden_leakage_field_present"] == 1


def test_schema_local_rejects_unsafe_or_ambiguous_conversion(tmp_path: Path) -> None:
    unsafe = _run_fixture(tmp_path / "unsafe", arg_schema={"type": "integer"}, value="4.2")
    assert unsafe["schema_local_non_live_repair_diagnostic_passed"] is False
    assert unsafe["counters"]["schema_local_unsafe_conversion_count"] == 1
    ambiguous = _run_fixture(tmp_path / "ambiguous", arg_schema={"type": "string", "enum": ["Red", "red"]}, value="RED")
    assert ambiguous["schema_local_non_live_repair_diagnostic_passed"] is False
    assert ambiguous["counters"]["schema_local_ambiguous_count"] == 1
