from __future__ import annotations

import json
from pathlib import Path

from scripts.check_schema_retrieval_rerank_feasibility_diagnostic import _case_rerank, build_report


def _fn(name: str, props: list[str]) -> dict:
    return {"name": name, "parameters": {"type": "object", "properties": {p: {"type": "string"} for p in props}, "required": props[:1]}}


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_schema_rerank_case_high_margin_from_prompt_and_params() -> None:
    entry = {
        "id": "case_1",
        "question": [[{"role": "user", "content": "Please search documents by query."}]],
        "function": [_fn("document_search", ["query"]), _fn("calendar_create", ["title"])],
    }
    capture = {"raw_response": {"choices": [{"message": {"tool_calls": [{"function": {"name": "unknown", "arguments": "{\"query\":\"x\"}"}}]}}]}}
    result = _case_rerank(entry, capture)
    assert result["schema_option_count"] == 2
    assert result["high_margin"] is True
    assert result["prompt_support"] is True
    assert result["parameter_support"] is True


def test_schema_rerank_report_stops_on_low_margin(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    category = "multi_turn_miss_func"
    base = raw_root / category / "baseline"
    rows = []
    captures = []
    results = []
    dataset = []
    for i in range(3):
        cid = f"case_{i}"
        captures.append({"case_id": cid, "category": category, "provider_route": "Chuangzhi/Novacode", "model_id": "gpt-5.2", "raw_response": {"choices": [{"message": {"tool_calls": [{"function": {"name": "unknown", "arguments": "{\"z\":\"1\"}"}}]}}]}})
        results.append({"id": cid, "result": [{"unknown": json.dumps({"z": "1"})}]})
        rows.append({"id": cid, "model_name": "alias", "test_category": category, "valid": False, "error": {"error_type": "multi_turn:execution_response_mismatch"}, "possible_answer": [{"redacted": True}]})
        dataset.append({"id": cid, "question": [[{"role": "user", "content": "neutral words"}]], "function": [_fn("alpha", ["x"]), _fn("beta", ["y"])]})
    _write_jsonl(base / "raw_response_capture_records.jsonl", captures)
    _write_jsonl(base / "bfcl" / "result" / "alias" / "multi_turn" / f"BFCL_v4_{category}_result.json", results)
    _write_jsonl(base / "bfcl" / "score" / "alias" / "multi_turn" / f"BFCL_v4_{category}_score.json", [{"accuracy": 0.0, "correct_count": 0, "total_count": 3}, *rows])
    dataset_path = tmp_path / "dataset.json"
    dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

    report = build_report(raw_root=raw_root, dataset_json=dataset_path, categories=category, output_json=tmp_path / "out.json", markdown_output=tmp_path / "out.md")
    counters = report["counters"]
    assert report["input_case_count"] == 3
    assert counters["audited_bucket_case_count"] == 3
    assert counters["single_schema_high_margin_count"] == 0
    assert counters["all_schema_scores_tied_or_low_margin_count"] == 3
    assert counters["uses_gold_tool_identity_count"] == 0
    assert report["stop_gates"]["passed"] is False
    assert report["decision"]["recommendation"] == "stop_no_yield_research_review"
    serialized = json.dumps(report, sort_keys=True)
    assert "possible_answer" not in serialized
    assert report["candidate_pool_authorized"] is False
    assert report["performance_evidence"] is False
