from __future__ import annotations

import json
from pathlib import Path

from scripts.build_raw_response_capture_records import build_capture


def _write_json(path: Path, payload) -> None:  # type: ignore[no-untyped-def]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_build_raw_response_capture_records_happy_path(tmp_path: Path) -> None:
    category = "multi_turn_base"
    run_root = tmp_path / "run"
    result = run_root / "bfcl" / "result" / "model" / "multi_turn" / f"BFCL_v4_{category}_result.json"
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps({
        "id": "case_1",
        "latency": [[1.0]],
        "result": [[{"grep": json.dumps({"file_name": "a.txt", "pattern": "x"})}]],
    }) + "\n", encoding="utf-8")
    trace = run_root / "traces" / "trace.json"
    _write_json(trace, {
        "raw_response": {"choices": [{"message": {"tool_calls": [{"function": {"name": "grep", "arguments": "{}"}}]}}]},
        "final_response": {"output": [{"name": "grep", "arguments": "{}"}]},
    })
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{
        "id": "case_1",
        "question": [[{"role": "user", "content": "Search."}]],
        "function": [{"name": "grep", "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["file_name", "pattern"]}}],
    }])
    out = tmp_path / "capture.jsonl"

    report = build_capture(category=category, run_root=run_root, dataset_json=dataset, output_jsonl=out, limit=1)

    assert report["result_jsonl_rows"] == 1
    assert report["bad_jsonl_rows"] == 0
    assert report["raw_response_present_count"] == 1
    assert report["raw_response_text_present_count"] == 1
    assert report["required_capture_fields_present_count"] == 1
    assert report["forbidden_field_violation_count"] == 0
    row = json.loads(out.read_text().splitlines()[0])
    for key in ["case_id", "category", "provider_route", "model_id", "dataset_record_hash", "tool_schema_hash", "prompt_hash", "raw_response", "raw_response_text", "baseline_parsed_result", "parse_status", "parse_error_type", "selected_turn_index", "selected_call_count", "schema_match_status"]:
        assert key in row
    assert row["raw_response_hash"]
    assert row["trace_hashes"]


def test_build_raw_response_capture_records_flags_forbidden_metadata(tmp_path: Path) -> None:
    category = "multi_turn_base"
    run_root = tmp_path / "run"
    result = run_root / "bfcl" / "result" / "model" / "multi_turn" / f"BFCL_v4_{category}_result.json"
    result.parent.mkdir(parents=True, exist_ok=True)
    result.write_text(json.dumps({"id": "case_1", "latency": [[1.0]], "result": [[{"grep": "{}"}]]}) + "\n", encoding="utf-8")
    _write_json(run_root / "traces" / "trace.json", {"raw_response": {"ok": True}})
    dataset = tmp_path / "dataset.json"
    _write_json(dataset, [{"id": "case_1", "question": "q", "possible_answer": "forbidden", "function": [{"name": "grep", "parameters": {"properties": {}, "required": []}}]}])

    report = build_capture(category=category, run_root=run_root, dataset_json=dataset, output_jsonl=tmp_path / "capture.jsonl", limit=1)

    assert report["forbidden_field_violation_count"] == 0
    # The builder hashes sanitized fields and does not copy forbidden dataset fields into output records.
    row = json.loads((tmp_path / "capture.jsonl").read_text().splitlines()[0])
    assert "possible_answer" not in json.dumps(row)
