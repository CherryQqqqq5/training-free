#!/usr/bin/env python3
"""Build raw-response capture records from BFCL result JSONL and proxy traces.

The output is raw and must stay under /tmp. It joins existing BFCL parsed result
rows with GRC proxy traces by request order, using the per-row latency structure
as the trace-count budget. It writes one capture record per BFCL result row with
raw response material and compact hashes for later tracked snapshots.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from scripts.build_explicit_literal_candidate_pool import (
    _dataset_records,
    _result_file,
    _result_rows,
    _schema_match,
    _selected_turn_calls,
    _tool_call_records,
)

FORBIDDEN_KEYS = {
    "gold", "expected", "answer", "ground_truth", "oracle", "score",
    "candidate", "repair", "reference", "possible_answer",
}


def _contains_forbidden_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in FORBIDDEN_KEYS:
                return True
            if _contains_forbidden_key(nested):
                return True
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _sanitize_for_hash(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _sanitize_for_hash(v) for k, v in value.items() if str(k) not in FORBIDDEN_KEYS}
    if isinstance(value, list):
        return [_sanitize_for_hash(item) for item in value]
    return value


def _hash_json(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _flatten_count(value: Any) -> int:
    if isinstance(value, list):
        return sum(_flatten_count(item) for item in value)
    return 1 if value is not None else 0


def _question_payload(entry: dict[str, Any]) -> Any:
    return entry.get("question") or entry.get("messages") or entry.get("prompt") or []


def _tool_schema_payload(entry: dict[str, Any]) -> Any:
    return entry.get("function") or entry.get("functions") or []


def _trace_sort_key(path: Path) -> tuple[float, str]:
    return (path.stat().st_mtime, path.name)


def _raw_response_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw
    return json.dumps(raw, ensure_ascii=False, sort_keys=True)


def _schema_match_status(entry: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    calls = _tool_call_records(row.get("result"))
    _historical, selected = _selected_turn_calls(calls)
    statuses: list[str] = []
    matched = 0
    for call in selected:
        fn, status, _reason, _names = _schema_match(entry, str(call.get("tool") or ""))
        statuses.append(status)
        if status == "matched" and fn:
            matched += 1
    return {
        "selected_turn_index": max([c.get("turn_index") for c in selected if c.get("turn_index") is not None], default=None),
        "selected_call_count": len(selected),
        "schema_match_status": "all_matched" if selected and matched == len(selected) else ("none_selected" if not selected else "partial_or_unmatched"),
        "schema_matched_selected_call_count": matched,
        "selected_call_statuses": statuses,
    }


def build_capture(
    *,
    category: str,
    run_root: Path,
    dataset_json: Path,
    output_jsonl: Path,
    provider_route: str = "Chuangzhi/Novacode",
    model_id: str = "gpt-5.2",
    limit: int | None = None,
) -> dict[str, Any]:
    dataset = _dataset_records(dataset_json)
    result_path = _result_file(run_root, category)
    rows = _result_rows(result_path)[:limit]
    trace_dir = run_root / "traces"
    traces = sorted(trace_dir.glob("*.json"), key=_trace_sort_key) if trace_dir.exists() else []
    trace_index = 0
    records: list[dict[str, Any]] = []
    bad_jsonl_rows = 0
    forbidden = 0
    missing_required_fields = 0

    for row in rows:
        case_id = str(row.get("id") or row.get("case_id") or "")
        entry = dataset.get(case_id, {})
        expected_traces = _flatten_count(row.get("latency")) or 1
        assigned_paths = traces[trace_index: trace_index + expected_traces]
        trace_index += expected_traces
        assigned = []
        for path in assigned_paths:
            try:
                assigned.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                bad_jsonl_rows += 1
        last = assigned[-1] if assigned else {}
        raw = last.get("raw_response") if isinstance(last, dict) else None
        raw_text = _raw_response_text(raw) if raw is not None else None
        final_response = last.get("final_response") if isinstance(last, dict) else None
        schema_status = _schema_match_status(entry, row) if entry else {"selected_turn_index": None, "selected_call_count": 0, "schema_match_status": "dataset_record_missing"}
        record = {
            "case_id": case_id,
            "category": category,
            "provider_route": provider_route,
            "model_id": model_id,
            "dataset_record_hash": _hash_json(_sanitize_for_hash(entry)) if entry else None,
            "tool_schema_hash": _hash_json(_sanitize_for_hash(_tool_schema_payload(entry))) if entry else None,
            "prompt_hash": _hash_json(_sanitize_for_hash(_question_payload(entry))) if entry else None,
            "raw_response": raw,
            "raw_response_text": raw_text,
            "baseline_parsed_result": row.get("result"),
            "parse_status": "parsed_from_bfcl_result" if row.get("result") is not None else "missing_result",
            "parse_error_type": None if row.get("result") is not None else "missing_result",
            "selected_turn_index": schema_status.get("selected_turn_index"),
            "selected_call_count": schema_status.get("selected_call_count"),
            "schema_match_status": schema_status.get("schema_match_status"),
            "trace_hashes": [_hash_json(item) for item in assigned],
            "raw_response_hash": _hash_json(raw) if raw is not None else None,
            "raw_response_text_hash": hashlib.sha256(raw_text.encode("utf-8")).hexdigest() if raw_text else None,
            "final_response_hash": _hash_json(final_response) if final_response is not None else None,
        }
        if _contains_forbidden_key({k: v for k, v in record.items() if k not in {"raw_response", "raw_response_text", "baseline_parsed_result"}}):
            forbidden += 1
        required = ["case_id", "category", "provider_route", "model_id", "dataset_record_hash", "tool_schema_hash", "prompt_hash", "baseline_parsed_result", "parse_status", "selected_call_count", "schema_match_status"]
        if any(record.get(key) in (None, "") for key in required) or (not record.get("raw_response") and not record.get("raw_response_text")):
            missing_required_fields += 1
        records.append(record)

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_jsonl.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records), encoding="utf-8")
    latest = max((p.stat().st_mtime for p in traces), default=0)
    return {
        "category": category,
        "run_root": str(run_root),
        "result_path": str(result_path) if result_path else None,
        "result_jsonl_rows": len(records),
        "bad_jsonl_rows": bad_jsonl_rows,
        "trace_count_available": len(traces),
        "trace_count_consumed": trace_index,
        "latest_trace_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(latest)) if latest else None,
        "raw_response_present_count": sum(1 for row in records if row.get("raw_response") is not None),
        "raw_response_text_present_count": sum(1 for row in records if row.get("raw_response_text")),
        "required_capture_fields_present_count": len(records) - missing_required_fields,
        "forbidden_field_violation_count": forbidden,
        "provider_route_counts": {provider_route: len(records)},
        "model_id_counts": {model_id: len(records)},
        "sample_hashes": [{"case_id": row["case_id"], "raw_response_hash": row.get("raw_response_hash"), "prompt_hash": row.get("prompt_hash"), "tool_schema_hash": row.get("tool_schema_hash")} for row in records[:5]],
        "output_jsonl": str(output_jsonl),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build raw-response capture records under /tmp from BFCL result and proxy traces.")
    parser.add_argument("--category", required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--dataset-json", type=Path, default=Path("/tmp/explicit_literal_pool/explicit_literal_dataset.json"))
    parser.add_argument("--output-jsonl", type=Path, required=True)
    parser.add_argument("--provider-route", default="Chuangzhi/Novacode")
    parser.add_argument("--model-id", default="gpt-5.2")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    report = build_capture(
        category=args.category,
        run_root=args.run_root,
        dataset_json=args.dataset_json,
        output_jsonl=args.output_jsonl,
        provider_route=args.provider_route,
        model_id=args.model_id,
        limit=args.limit,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
