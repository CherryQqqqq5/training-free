from __future__ import annotations

import json
from pathlib import Path

from scripts.check_baseline_only_scored_failure_taxonomy_audit import build_report


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_baseline_only_scored_failure_taxonomy_compact_no_gold_emission(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    category = "multi_turn_miss_func"
    base = raw_root / category / "baseline"
    _write_jsonl(base / "raw_response_capture_records.jsonl", [
        {
            "case_id": "case_fail",
            "category": category,
            "provider_route": "Chuangzhi/Novacode",
            "model_id": "gpt-5.2",
            "raw_response": {"choices": [{"message": {"tool_calls": [{"function": {"name": "grep", "arguments": "{\"file_name\":\"a.txt\",\"pattern\":\"x\"}"}}]}}]},
            "baseline_parsed_result": [{"grep": json.dumps({"file_name": "a.txt", "pattern": "x"})}],
        },
        {
            "case_id": "case_success",
            "category": category,
            "provider_route": "Chuangzhi/Novacode",
            "model_id": "gpt-5.2",
            "raw_response": {"choices": [{"message": {"tool_calls": [{"function": {"name": "grep", "arguments": "{\"file_name\":\"b.txt\",\"pattern\":\"y\"}"}}]}}]},
            "baseline_parsed_result": [{"grep": json.dumps({"file_name": "b.txt", "pattern": "y"})}],
        },
    ])
    _write_jsonl(base / "bfcl" / "result" / "alias" / "multi_turn" / f"BFCL_v4_{category}_result.json", [
        {"id": "case_fail", "result": [{"grep": json.dumps({"file_name": "a.txt", "pattern": "x"})}]},
        {"id": "case_success", "result": [{"grep": json.dumps({"file_name": "b.txt", "pattern": "y"})}]},
    ])
    _write_jsonl(base / "bfcl" / "score" / "alias" / "multi_turn" / f"BFCL_v4_{category}_score.json", [
        {"accuracy": 0.5, "correct_count": 1, "total_count": 2},
        {
            "id": "case_fail",
            "model_name": "alias",
            "test_category": category,
            "valid": False,
            "error": {"error_type": "multi_turn:execution_response_mismatch", "error_message": "redacted"},
            "possible_answer": [{"redacted": True}],
            "prompt": "must not be emitted",
            "model_result_raw": [{"redacted": True}],
        },
    ])
    dataset = tmp_path / "dataset.json"
    dataset.write_text(json.dumps([
        {
            "id": "case_fail",
            "question": [[{"role": "user", "content": "Use grep."}]],
            "function": [{"name": "grep", "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["file_name", "pattern"]}}],
        },
        {
            "id": "case_success",
            "question": [[{"role": "user", "content": "Use grep."}]],
            "function": [{"name": "grep", "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["file_name", "pattern"]}}],
        },
    ]), encoding="utf-8")

    report = build_report(
        raw_root=raw_root,
        dataset_json=dataset,
        categories=category,
        output_json=tmp_path / "audit.json",
        markdown_output=tmp_path / "audit.md",
    )

    counters = report["counters"]
    assert counters["audited_case_count"] == 2
    assert counters["scored_case_count"] == 2
    assert counters["source_score_case_overlap_count"] == 1
    assert counters["missing_score_count"] == 0
    assert counters["route_model_matched_count"] == 1
    assert counters["forbidden_field_violation_count"] == 0
    assert counters["baseline_success_count"] == 1
    assert counters["baseline_failure_count"] == 1
    assert counters["failure_with_schema_valid_selected_calls"] == 1
    assert report["raw_score_gold_bearing_rows_read_count"] == 1
    serialized = json.dumps(report, sort_keys=True)
    assert "must not be emitted" not in serialized
    assert "possible_answer" not in serialized
    assert report["performance_evidence"] is False
    assert report["candidate_pool_authorized"] is False
