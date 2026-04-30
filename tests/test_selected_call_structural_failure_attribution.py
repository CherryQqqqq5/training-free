from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.check_selected_call_structural_failure_attribution import build_report

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_selected_call_structural_failure_attribution.py"


def _write_json(path: Path, payload) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path, *, row_extra: dict, result) -> tuple[Path, Path]:
    category = "multi_turn_miss_func"
    source_root = tmp_path / "source" / category / "baseline"
    result_path = source_root / "bfcl" / "result" / "model" / "multi_turn" / f"BFCL_v4_{category}_result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    row = {"id": "case_1", "result": result}
    row.update(row_extra)
    result_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    source_manifest = tmp_path / "source_manifest.json"
    _write_json(source_manifest, {"category_status": [{"category": category, "existing_source_roots": [str(source_root)]}]})
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "case_1",
        "question": [[{"role": "user", "content": "Use grep."}]],
        "function": [{
            "name": "grep",
            "parameters": {
                "type": "object",
                "properties": {"file_name": {"type": "string"}, "pattern": {"type": "string"}},
                "required": ["file_name", "pattern"],
            },
        }],
    }])
    return source_manifest, dataset


def _run(tmp_path: Path, *, row_extra: dict, result) -> dict:
    source_manifest, dataset = _fixture(tmp_path, row_extra=row_extra, result=result)
    return build_report(
        dataset_json=dataset,
        source_manifest=source_manifest,
        categories="multi_turn_miss_func",
        output_json=tmp_path / "out.json",
        markdown_output=tmp_path / "out.md",
    )


def test_selected_call_structural_help() -> None:
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


def test_selected_call_structural_missing_raw_response_fails_closed(tmp_path: Path) -> None:
    report = _run(tmp_path, row_extra={}, result=[{"grep": json.dumps({"file_name": "a.txt", "pattern": "x"})}])
    assert report["selected_call_structural_failure_attribution_passed"] is False
    assert report["counters"]["raw_response_present_count"] == 0
    assert report["counters"]["selected_call_count"] == 1
    assert report["counters"]["schema_matched_selected_call_count"] == 1
    assert report["counters"]["schema_valid_required_args_present_count"] == 1
    assert "raw_response_field_missing_for_structural_attribution" in report["blockers"]
    assert report["counters"]["reject_reason_counts"]["raw_response_missing_for_structural_attribution"] == 1


def test_selected_call_structural_final_before_tool_guard_eligible(tmp_path: Path) -> None:
    raw = 'Done. grep({"file_name":"a.txt","pattern":"x"})'
    report = _run(tmp_path, row_extra={"raw_response": raw}, result=["Done."])
    counters = report["counters"]
    assert report["selected_call_structural_failure_attribution_passed"] is True
    assert counters["raw_response_present_count"] == 1
    assert counters["rows_with_final_text_and_tool_like_payload"] == 1
    assert counters["final_before_tool_guard_eligible_count"] == 1
    assert report["eligible_structural_records"][0]["diagnostic"] == "final_before_tool_guard"
    assert report["candidate_pool_authorized"] is False
    assert report["performance_evidence"] is False


def test_selected_call_structural_multiple_payloads_reject(tmp_path: Path) -> None:
    raw = 'grep({"file_name":"a.txt","pattern":"x"}) grep({"file_name":"b.txt","pattern":"y"})'
    report = _run(tmp_path, row_extra={"raw_response": raw}, result=["Done."])
    assert report["selected_call_structural_failure_attribution_passed"] is False
    assert report["counters"]["rows_with_multiple_tool_like_payloads"] == 1
    assert report["counters"]["reject_reason_counts"]["multiple_tool_like_payloads"] == 1


def test_selected_call_structural_unparseable_arguments_reject(tmp_path: Path) -> None:
    raw = {"name": "grep", "arguments": "{not-json"}
    report = _run(tmp_path, row_extra={"raw_response": raw}, result=["Done."])
    assert report["selected_call_structural_failure_attribution_passed"] is False
    assert report["counters"]["rows_with_unparseable_arguments"] == 1
    assert report["counters"]["reject_reason_counts"]["unparseable_arguments"] == 1
