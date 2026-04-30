from __future__ import annotations

import json
from pathlib import Path

from scripts.check_raw_payload_schema_not_matched_subtyping_audit import _classify_tool_name, build_report


def _fn(name: str) -> dict:
    return {"name": name, "parameters": {"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]}}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_raw_payload_subtyping_classifier_unique_modes() -> None:
    assert _classify_tool_name("searchtool", {"function": [_fn("SearchTool")]}) == ("case_insensitive_unique_match", True, False)
    assert _classify_tool_name("search-tool", {"function": [_fn("search_tool")]}) == ("punctuation_or_separator_unique_match", True, False)
    assert _classify_tool_name("provider/search", {"function": [_fn("search")]}) == ("provider_namespace_or_path_alias_unique_match", True, False)
    assert _classify_tool_name("pkg.search", {"function": [_fn("search")]}) == ("qualified_short_name_unique_match", True, False)
    assert _classify_tool_name("missing", {"function": [_fn("search")]}) == ("no_schema_name_candidate", False, False)
    assert _classify_tool_name("search", {"function": [_fn("pkg.search"), _fn("other.search")]}) == ("multiple_schema_name_candidates", False, True)


def test_raw_payload_schema_not_matched_subtyping_report_fail_closed(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    category = "multi_turn_miss_func"
    base = raw_root / category / "baseline"
    _write_jsonl(base / "raw_response_capture_records.jsonl", [
        {
            "case_id": "case_1",
            "category": category,
            "provider_route": "Chuangzhi/Novacode",
            "model_id": "gpt-5.2",
            "raw_response": {"choices": [{"message": {"tool_calls": [{"function": {"name": "totally_unknown", "arguments": "{\"x\":\"1\"}"}}]}}]},
            "baseline_parsed_result": [{"totally_unknown": json.dumps({"x": "1"})}],
        }
    ])
    _write_jsonl(base / "bfcl" / "result" / "alias" / "multi_turn" / f"BFCL_v4_{category}_result.json", [
        {"id": "case_1", "result": [{"totally_unknown": json.dumps({"x": "1"})}]}
    ])
    _write_jsonl(base / "bfcl" / "score" / "alias" / "multi_turn" / f"BFCL_v4_{category}_score.json", [
        {"accuracy": 0.0, "correct_count": 0, "total_count": 1},
        {"id": "case_1", "model_name": "alias", "test_category": category, "valid": False, "error": {"error_type": "multi_turn:execution_response_mismatch"}, "possible_answer": [{"redacted": True}]},
    ])
    dataset = tmp_path / "dataset.json"
    dataset.write_text(json.dumps([{"id": "case_1", "question": [[{"role": "user", "content": "x"}]], "function": [_fn("search")]}]), encoding="utf-8")

    report = build_report(raw_root=raw_root, dataset_json=dataset, categories=category, output_json=tmp_path / "out.json", markdown_output=tmp_path / "out.md")
    counters = report["counters"]
    assert counters["raw_payload_schema_not_matched_failure_count"] == 1
    assert counters["input_case_count"] == 1
    assert counters["audited_bucket_case_count"] == 1
    assert counters["raw_response_present_count"] == 1
    assert counters["dataset_schema_present_count"] == 1
    assert counters["emitted_tool_name_exact_schema_miss_count"] == 1
    assert counters["no_schema_name_candidate_count"] == 1
    assert counters["tool_selection_semantic_mismatch_count"] == 1
    assert counters["normalization_uses_gold_count"] == 0
    assert counters["normalization_changes_arguments_count"] == 0
    assert counters["normalization_changes_tool_order_count"] == 0
    assert counters["normalization_changes_call_count"] == 0
    assert counters["deterministic_source_schema_only_possible_count"] == 0
    assert report["decision"]["recommendation"] == "stop_no_yield_research_review"
    serialized = json.dumps(report, sort_keys=True)
    assert "possible_answer" not in serialized
    assert report["candidate_pool_authorized"] is False
    assert report["performance_evidence"] is False
