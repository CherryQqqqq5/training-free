#!/usr/bin/env python3
"""Offline selected-call structural failure attribution diagnostic.

This diagnostic uses existing source result JSONL only. It never calls a
provider, BFCL, a model, or a scorer. Structural repair eligibility is reported
only when a raw model response contains a unique schema-matched tool-like payload
with existing arguments and a deterministic parse/serialization path.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from scripts.build_explicit_literal_candidate_pool import (
    _dataset_records,
    _parse_call_args,
    _parse_categories,
    _properties,
    _required_args,
    _result_file,
    _result_rows,
    _schema_match,
    _selected_turn_calls,
    _source_roots,
    _tool_call_records,
)

DEFAULT_DATASET_JSON = Path("/tmp/explicit_literal_pool/explicit_literal_dataset.json")
DEFAULT_OUTPUT_JSON = Path("outputs/artifacts/stage1_bfcl_acceptance/selected_call_structural_failure_attribution.json")
DEFAULT_OUTPUT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/selected_call_structural_failure_attribution.md")
RAW_RESPONSE_KEYS = ("raw_response", "model_raw_response", "assistant_raw_response", "response_text", "raw_output")
FORBIDDEN_KEYS = {
    "gold", "answer", "expected", "ground_truth", "oracle", "checker", "reference",
    "possible_answer", "score", "candidate", "repair",
}


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _default_source_manifest() -> dict[str, Any]:
    roots = []
    for category in ("multi_turn_miss_func", "multi_turn_base", "multi_turn_long_context"):
        root = Path(f"/tmp/bfcl_source_collection/{category}/baseline")
        if root.exists():
            roots.append({"category": category, "existing_source_roots": [str(root)]})
    return {"category_status": roots}


def _raw_response(row: dict[str, Any]) -> Any:
    for key in RAW_RESPONSE_KEYS:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return None


def _schema_valid_args(fn: dict[str, Any], args: dict[str, Any]) -> bool:
    props = _properties(fn)
    for arg in _required_args(fn):
        if arg not in args:
            return False
    for key in args:
        if key not in props:
            continue
        schema = props.get(key) if isinstance(props.get(key), dict) else {}
        typ = str(schema.get("type") or "").lower()
        val = args[key]
        if typ in {"", "string"} and not isinstance(val, str):
            return False
        if typ == "integer" and (not isinstance(val, int) or isinstance(val, bool)):
            return False
        if typ == "number" and (not isinstance(val, (int, float)) or isinstance(val, bool)):
            return False
        if typ == "boolean" and not isinstance(val, bool):
            return False
        if typ == "array" and not isinstance(val, list):
            return False
        if typ == "object" and not isinstance(val, dict):
            return False
    return True


def _walk_tool_payloads(value: Any) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []

    def add(tool: str, args: Any, malformed: bool = False) -> None:
        parse_failed = False
        if isinstance(args, str):
            try:
                parsed_raw = json.loads(args)
                parse_failed = not isinstance(parsed_raw, dict)
            except Exception:
                parse_failed = True
        parsed = _parse_call_args(args)
        payloads.append({"tool": tool, "args": parsed, "malformed": malformed or parse_failed or not isinstance(parsed, dict)})

    def walk(item: Any) -> None:
        if isinstance(item, list):
            for nested in item:
                walk(nested)
            return
        if not isinstance(item, dict):
            return
        if item.get("name") and ("arguments" in item or "args" in item):
            add(str(item["name"]), item.get("arguments", item.get("args")))
            return
        if item.get("function") and isinstance(item["function"], dict):
            fn = item["function"]
            if fn.get("name") and "arguments" in fn:
                add(str(fn["name"]), fn.get("arguments"))
                return
        for key, raw_args in item.items():
            if isinstance(raw_args, (dict, str)):
                add(str(key), raw_args)
    walk(value)
    return payloads


def _extract_tool_like_payloads(raw: Any) -> tuple[list[dict[str, Any]], bool, bool]:
    """Return payloads, malformed_json_seen, final_text_present."""
    malformed = False
    final_text = False
    if isinstance(raw, (dict, list)):
        return _walk_tool_payloads(raw), False, False
    if not isinstance(raw, str):
        return [], False, False
    text = raw.strip()
    if not text:
        return [], False, False
    try:
        parsed = json.loads(text)
        return _walk_tool_payloads(parsed), False, False
    except Exception:
        pass
    payloads: list[dict[str, Any]] = []
    spans: list[tuple[int, int]] = []
    # Deterministic function-name(JSON-object) extraction. This is deliberately
    # narrow and not semantic/fuzzy.
    pattern = re.compile(r"\b([A-Za-z_][A-Za-z0-9_\.]*)\s*\(\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})\s*\)")
    for match in pattern.finditer(text):
        tool = match.group(1)
        raw_args = match.group(2)
        try:
            args = json.loads(raw_args)
        except Exception:
            malformed = True
            args = {}
        payloads.append({"tool": tool, "args": args if isinstance(args, dict) else {}, "malformed": not isinstance(args, dict)})
        spans.append(match.span())
    if not payloads and ("{" in text or "}" in text or "tool" in text.lower() or "arguments" in text.lower()):
        malformed = True
    remainder = text
    for start, end in reversed(spans):
        remainder = remainder[:start] + remainder[end:]
    final_text = bool(re.sub(r"[\s`.,;:!-]", "", remainder))
    return payloads, malformed, final_text


def _empty_category(category: str) -> dict[str, Any]:
    return {"category": category, "result_jsonl_rows": 0, "selected_call_count": 0, "reject_reason_counts": {}}


def build_report(
    *,
    dataset_json: Path = DEFAULT_DATASET_JSON,
    source_manifest: Path | None = None,
    source_root: Path = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1"),
    categories: str | list[str] | None = None,
    output_json: Path = DEFAULT_OUTPUT_JSON,
    markdown_output: Path = DEFAULT_OUTPUT_MD,
    compact: bool = False,
) -> dict[str, Any]:
    requested_categories = _parse_categories(categories) or ["multi_turn_miss_func", "multi_turn_base", "multi_turn_long_context"]
    source = _read_json(source_manifest, {}) if source_manifest else _default_source_manifest()
    dataset = _dataset_records(dataset_json)
    counters: dict[str, int] = {
        "result_jsonl_rows": 0,
        "raw_response_present_count": 0,
        "selected_call_count": 0,
        "schema_matched_selected_call_count": 0,
        "schema_valid_required_args_present_count": 0,
        "rows_with_no_tool_call": 0,
        "rows_with_final_text_only": 0,
        "rows_with_final_text_and_tool_like_payload": 0,
        "rows_with_malformed_tool_call_json": 0,
        "rows_with_unparseable_arguments": 0,
        "rows_with_multiple_tool_like_payloads": 0,
        "malformed_tool_call_repair_eligible_count": 0,
        "final_before_tool_guard_eligible_count": 0,
    }
    reject_reason_counts: dict[str, int] = {}
    blockers: list[str] = []
    records: list[dict[str, Any]] = []
    category_rows: dict[str, dict[str, Any]] = {}

    def reject(reason: str, category: str | None = None) -> None:
        reject_reason_counts[reason] = reject_reason_counts.get(reason, 0) + 1
        if category:
            bucket = category_rows.setdefault(category, _empty_category(category))
            bucket["reject_reason_counts"][reason] = bucket["reject_reason_counts"].get(reason, 0) + 1

    if not dataset_json.exists() or not dataset:
        blockers.append("dataset_json_missing_or_empty")
    if source_manifest and not source_manifest.exists():
        blockers.append("source_manifest_missing")

    for category, root in _source_roots(source or {}, source_root, requested_categories):
        bucket = category_rows.setdefault(category, _empty_category(category))
        result_path = _result_file(root, category)
        rows = _result_rows(result_path)
        counters["result_jsonl_rows"] += len(rows)
        bucket["result_jsonl_rows"] += len(rows)
        if result_path is None:
            reject("missing_source_result", category)
            continue
        for row in rows:
            case_id = str(row.get("id") or row.get("case_id") or "")
            entry = dataset.get(case_id)
            if not entry:
                reject("dataset_record_missing", category)
                continue
            metadata = {key: value for key, value in row.items() if key not in {"result", *RAW_RESPONSE_KEYS}}
            if _contains_forbidden_key(entry) or _contains_forbidden_key(metadata):
                reject("forbidden_leakage_field_present", category)
                continue
            calls = _tool_call_records(row.get("result"))
            _historical, selected = _selected_turn_calls(calls)
            counters["selected_call_count"] += len(selected)
            bucket["selected_call_count"] += len(selected)
            for call in selected:
                fn, status, _reason, _names = _schema_match(entry, str(call.get("tool") or ""))
                if status == "matched" and fn:
                    counters["schema_matched_selected_call_count"] += 1
                    if _schema_valid_args(fn, call.get("args") or {}):
                        counters["schema_valid_required_args_present_count"] += 1
            raw = _raw_response(row)
            if raw is None:
                reject("raw_response_missing_for_structural_attribution", category)
                continue
            counters["raw_response_present_count"] += 1
            payloads, malformed, final_text = _extract_tool_like_payloads(raw)
            if malformed:
                counters["rows_with_malformed_tool_call_json"] += 1
            if not payloads:
                counters["rows_with_no_tool_call"] += 1
                if final_text or isinstance(raw, str):
                    counters["rows_with_final_text_only"] += 1
                reject("no_tool_like_payload", category)
                continue
            if len(payloads) > 1:
                counters["rows_with_multiple_tool_like_payloads"] += 1
                reject("multiple_tool_like_payloads", category)
                continue
            payload = payloads[0]
            if payload.get("malformed"):
                counters["rows_with_unparseable_arguments"] += 1
                reject("unparseable_arguments", category)
                continue
            fn, status, _reason, _names = _schema_match(entry, payload["tool"])
            if status != "matched" or not fn:
                reject("raw_payload_schema_not_matched", category)
                continue
            if not _schema_valid_args(fn, payload.get("args") or {}):
                reject("raw_payload_args_not_schema_valid", category)
                continue
            selected_tools = [str(call.get("tool")) for call in selected]
            if malformed:
                counters["malformed_tool_call_repair_eligible_count"] += 1
                records.append({"case_id": case_id, "category": category, "diagnostic": "malformed_tool_call_serialization", "tool": payload["tool"], "diagnostic_only": True})
            elif final_text:
                counters["rows_with_final_text_and_tool_like_payload"] += 1
                if not selected_tools:
                    counters["final_before_tool_guard_eligible_count"] += 1
                    records.append({"case_id": case_id, "category": category, "diagnostic": "final_before_tool_guard", "tool": payload["tool"], "diagnostic_only": True})
                else:
                    reject("selected_adapter_already_took_tool_call", category)
            else:
                reject("raw_payload_valid_no_structural_failure", category)

    if counters["raw_response_present_count"] == 0:
        blockers.append("raw_response_field_missing_for_structural_attribution")
    if not records:
        blockers.append("structural_repair_eligible_count_zero")
    passed = bool(records) and not blockers
    report = {
        "report_scope": "selected_call_structural_failure_attribution",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "offline_only": True,
        "diagnostic_only": True,
        "does_not_call_provider": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_call_scorer": True,
        "candidate_pool_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "huawei_acceptance_ready": False,
        "sota_3pp_claim_ready": False,
        "does_not_invent_tool_function_arg_or_value": True,
        "raw_traces_remain_untracked": True,
        "forbidden_fields_not_used": sorted(FORBIDDEN_KEYS),
        "dataset_json": str(dataset_json),
        "source_manifest": str(source_manifest) if source_manifest else "default_tmp_batch1_batch2_roots",
        "requested_categories": requested_categories,
        "counters": {**counters, "reject_reason_counts": reject_reason_counts},
        "category_summaries": list(category_rows.values()),
        "eligible_structural_records": records[:25] if compact else records,
        "eligible_structural_record_count": len(records),
        "blockers": blockers,
        "selected_call_structural_failure_attribution_passed": passed,
        "next_required_action": "research_review_required_missing_raw_response_field" if counters["raw_response_present_count"] == 0 else "research_review_required_do_not_lower_standards",
    }
    _write_json(output_json, report)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_markdown(report), encoding="utf-8")
    return report


def _markdown(report: dict[str, Any]) -> str:
    c = report["counters"]
    keys = [
        "result_jsonl_rows",
        "raw_response_present_count",
        "selected_call_count",
        "schema_matched_selected_call_count",
        "schema_valid_required_args_present_count",
        "rows_with_no_tool_call",
        "rows_with_final_text_only",
        "rows_with_final_text_and_tool_like_payload",
        "rows_with_malformed_tool_call_json",
        "rows_with_unparseable_arguments",
        "rows_with_multiple_tool_like_payloads",
        "malformed_tool_call_repair_eligible_count",
        "final_before_tool_guard_eligible_count",
    ]
    lines = [
        "# Selected-Call Structural Failure Attribution",
        "",
        "This is an offline diagnostic artifact only. It is not candidate-pool, scorer, performance, SOTA, or Huawei acceptance evidence.",
        "",
        f"- diagnostic_only: `{str(report['diagnostic_only']).lower()}`",
        f"- candidate_pool_authorized: `{str(report['candidate_pool_authorized']).lower()}`",
        f"- scorer_authorized: `{str(report['scorer_authorized']).lower()}`",
        f"- performance_evidence: `{str(report['performance_evidence']).lower()}`",
        f"- huawei_acceptance_ready: `{str(report['huawei_acceptance_ready']).lower()}`",
        f"- sota_3pp_claim_ready: `{str(report['sota_3pp_claim_ready']).lower()}`",
        "- raw traces remain untracked; no provider/scorer/source collection was run",
        "",
        "## Counters",
        "",
        "| counter | value |",
        "| --- | ---: |",
    ]
    for key in keys:
        lines.append(f"| {key} | {c.get(key, 0)} |")
    lines.extend([
        "",
        f"- reject_reason_counts: `{json.dumps(c.get('reject_reason_counts', {}), sort_keys=True)}`",
        f"- blockers: `{json.dumps(report.get('blockers', []), sort_keys=True)}`",
        f"- next_required_action: `{report.get('next_required_action')}`",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline selected-call structural failure attribution diagnostic.")
    parser.add_argument("--dataset-json", type=Path, default=DEFAULT_DATASET_JSON)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--source-root", type=Path, default=Path("outputs/artifacts/bfcl_ctspc_source_pool_v1"))
    parser.add_argument("--categories", default="multi_turn_miss_func,multi_turn_base,multi_turn_long_context")
    parser.add_argument("--output", "--output-json", dest="output_json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = build_report(
        dataset_json=args.dataset_json,
        source_manifest=args.source_manifest,
        source_root=args.source_root,
        categories=args.categories,
        output_json=args.output_json,
        markdown_output=args.markdown_output,
        compact=args.compact,
    )
    if args.compact:
        print(json.dumps({"passed": report["selected_call_structural_failure_attribution_passed"], "counters": report["counters"], "blockers": report["blockers"]}, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["selected_call_structural_failure_attribution_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
