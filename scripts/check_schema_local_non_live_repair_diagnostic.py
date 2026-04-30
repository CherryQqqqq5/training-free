#!/usr/bin/env python3
"""Offline diagnostic gate for deterministic schema-local non-live repair.

The checker inspects existing BFCL source result JSONL and sanitized dataset
schemas only. It identifies local, deterministic value conversions for canonical
arguments that are already present in baseline emitted args but locally invalid
for the schema. It does not call a provider, BFCL, a model, or a scorer, and it
never emits candidate-pool rules.
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
DEFAULT_OUTPUT_JSON = Path("outputs/artifacts/stage1_bfcl_acceptance/schema_local_non_live_repair_diagnostic.json")
DEFAULT_OUTPUT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/schema_local_non_live_repair_diagnostic.md")
FORBIDDEN_KEYS = {
    "gold",
    "answer",
    "expected",
    "ground_truth",
    "oracle",
    "checker",
    "reference",
    "possible_answer",
    "score",
    "candidate",
    "repair",
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
    elif isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _default_source_manifest() -> dict[str, Any]:
    roots = []
    for category in ("multi_turn_miss_func", "multi_turn_base", "multi_turn_long_context"):
        root = Path(f"/tmp/bfcl_source_collection/{category}/baseline")
        if root.exists():
            roots.append({"category": category, "existing_source_roots": [str(root)]})
    return {"category_status": roots}


def _schema_for_arg(fn: dict[str, Any], arg: str) -> dict[str, Any]:
    schema = _properties(fn).get(arg)
    return schema if isinstance(schema, dict) else {}


def _json_type_valid(value: Any, schema: dict[str, Any]) -> bool:
    expected = str(schema.get("type") or "").lower()
    if expected in {"", "string"}:
        ok = isinstance(value, str)
    elif expected == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif expected == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif expected == "boolean":
        ok = isinstance(value, bool)
    elif expected == "array":
        ok = isinstance(value, list)
    elif expected == "object":
        ok = isinstance(value, dict)
    else:
        ok = False
    enum = schema.get("enum")
    if ok and isinstance(enum, list):
        return value in enum
    return ok


def _scalar_matches_item_schema(value: Any, item_schema: dict[str, Any]) -> bool:
    return _json_type_valid(value, item_schema if isinstance(item_schema, dict) else {})


def _conversion_candidates(value: Any, schema: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    """Return deterministic local conversions and reject reasons."""
    expected = str(schema.get("type") or "").lower()
    enum = schema.get("enum")
    candidates: list[dict[str, Any]] = []
    reasons: list[str] = []

    if _json_type_valid(value, schema):
        return [], ["schema_local_noop_already_valid"]

    if expected == "integer" and isinstance(value, str):
        raw = value.strip()
        if re.fullmatch(r"[-+]?\d+", raw):
            converted = int(raw)
            if _json_type_valid(converted, schema):
                candidates.append({"conversion": "numeric_string_to_integer", "converted_value_preview": converted})
            else:
                reasons.append("converted_value_not_schema_valid")
        else:
            reasons.append("schema_local_unsafe_conversion")
    elif expected == "number" and isinstance(value, str):
        raw = value.strip()
        try:
            converted_num = float(raw)
        except ValueError:
            converted_num = None
        if converted_num is not None and re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", raw):
            if _json_type_valid(converted_num, schema):
                candidates.append({"conversion": "numeric_string_to_number", "converted_value_preview": converted_num})
            else:
                reasons.append("converted_value_not_schema_valid")
        else:
            reasons.append("schema_local_unsafe_conversion")
    elif expected == "boolean" and isinstance(value, str) and value in {"true", "false"}:
        converted_bool = value == "true"
        if _json_type_valid(converted_bool, schema):
            candidates.append({"conversion": "boolean_string", "converted_value_preview": converted_bool})
        else:
            reasons.append("converted_value_not_schema_valid")
    elif isinstance(enum, list) and isinstance(value, str):
        matches = [item for item in enum if isinstance(item, str) and item.lower() == value.lower()]
        if len(matches) == 1:
            candidates.append({"conversion": "enum_case_normalization", "converted_value_preview": matches[0]})
        elif len(matches) > 1:
            reasons.append("schema_local_ambiguous")
        else:
            reasons.append("schema_local_no_conversion")
    elif expected == "array" and not isinstance(value, list):
        item_schema = schema.get("items") or {}
        if _scalar_matches_item_schema(value, item_schema if isinstance(item_schema, dict) else {}):
            converted_array = [value]
            if _json_type_valid(converted_array, schema):
                candidates.append({"conversion": "singleton_array_wrap", "converted_value_preview": converted_array})
            else:
                reasons.append("converted_value_not_schema_valid")
        else:
            reasons.append("schema_local_unsafe_conversion")
    else:
        reasons.append("schema_local_no_conversion")

    if len(candidates) > 1:
        return [], ["schema_local_ambiguous"]
    return candidates, reasons


def _empty_category(category: str) -> dict[str, Any]:
    return {
        "category": category,
        "result_jsonl_rows": 0,
        "selected_call_count": 0,
        "schema_local_repair_eligible_count": 0,
        "reject_reason_counts": {},
    }


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
        "selected_call_count": 0,
        "selected_calls_with_function_schema": 0,
        "selected_calls_with_required_args": 0,
        "required_args_present_count": 0,
        "schema_local_checked_arg_count": 0,
        "schema_local_type_mismatch_count": 0,
        "numeric_string_to_integer_candidate_count": 0,
        "numeric_string_to_number_candidate_count": 0,
        "boolean_string_candidate_count": 0,
        "enum_case_normalization_candidate_count": 0,
        "singleton_array_wrap_candidate_count": 0,
        "schema_local_candidate_count": 0,
        "schema_local_repair_eligible_count": 0,
        "schema_local_ambiguous_count": 0,
        "schema_local_unsafe_conversion_count": 0,
        "schema_local_noop_already_valid_count": 0,
    }
    reject_reason_counts: dict[str, int] = {}
    blockers: list[str] = []
    records: list[dict[str, Any]] = []
    category_rows: dict[str, dict[str, Any]] = {}

    def reject(reason: str, category: str | None = None) -> None:
        reject_reason_counts[reason] = reject_reason_counts.get(reason, 0) + 1
        if reason == "schema_local_ambiguous":
            counters["schema_local_ambiguous_count"] += 1
        if reason == "schema_local_unsafe_conversion":
            counters["schema_local_unsafe_conversion_count"] += 1
        if reason == "schema_local_noop_already_valid":
            counters["schema_local_noop_already_valid_count"] += 1
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
            metadata = {key: value for key, value in row.items() if key != "result"}
            if _contains_forbidden_key(entry) or _contains_forbidden_key(metadata):
                reject("forbidden_leakage_field_present", category)
                continue
            calls = _tool_call_records(row.get("result"))
            _historical, selected = _selected_turn_calls(calls)
            counters["selected_call_count"] += len(selected)
            bucket["selected_call_count"] += len(selected)
            for call in selected:
                fn, status, _reason, _candidate_names = _schema_match(entry, str(call.get("tool") or ""))
                if status == "schema_function_alias_not_unique":
                    reject("schema_function_alias_not_unique", category)
                    continue
                if not fn:
                    reject("function_schema_not_matched", category)
                    continue
                counters["selected_calls_with_function_schema"] += 1
                required = _required_args(fn)
                if not required:
                    reject("schema_required_empty", category)
                    continue
                counters["selected_calls_with_required_args"] += 1
                args = call.get("args") or {}
                if not isinstance(args, dict):
                    reject("emitted_args_not_object", category)
                    continue
                for arg in required:
                    if arg not in args:
                        reject("canonical_arg_absent", category)
                        continue
                    counters["required_args_present_count"] += 1
                    counters["schema_local_checked_arg_count"] += 1
                    value = args[arg]
                    schema = _schema_for_arg(fn, arg)
                    conversions, reasons = _conversion_candidates(value, schema)
                    if not conversions:
                        for reason in reasons:
                            reject(reason, category)
                        continue
                    counters["schema_local_type_mismatch_count"] += 1
                    if len(conversions) != 1:
                        reject("schema_local_ambiguous", category)
                        continue
                    conv = conversions[0]
                    conversion = conv["conversion"]
                    counter_name = {
                        "numeric_string_to_integer": "numeric_string_to_integer_candidate_count",
                        "numeric_string_to_number": "numeric_string_to_number_candidate_count",
                        "boolean_string": "boolean_string_candidate_count",
                        "enum_case_normalization": "enum_case_normalization_candidate_count",
                        "singleton_array_wrap": "singleton_array_wrap_candidate_count",
                    }[conversion]
                    counters[counter_name] += 1
                    counters["schema_local_candidate_count"] += 1
                    counters["schema_local_repair_eligible_count"] += 1
                    bucket["schema_local_repair_eligible_count"] += 1
                    records.append({
                        "case_id": case_id,
                        "category": category,
                        "diagnostic_only": True,
                        "value_provenance": "baseline_emitted_args",
                        "schema_provenance": "dataset_tool_schema",
                        "function": str(fn.get("name") or call.get("tool")),
                        "emitted_tool": str(call.get("tool")),
                        "canonical_arg": arg,
                        "conversion": conversion,
                        "converted_value_preview": conv.get("converted_value_preview"),
                        "turn_index": call.get("turn_index"),
                        "step_index": call.get("step_index"),
                        "call_index": call.get("call_index"),
                        "tool_choice_mutation": False,
                        "trajectory_mutation": False,
                        "unrelated_arg_mutation": False,
                        "postcondition_or_execution_feedback_used": False,
                    })

    if not records:
        blockers.append("schema_local_repair_eligible_count_zero")
    passed = bool(records) and not blockers
    report = {
        "report_scope": "schema_local_non_live_repair_diagnostic",
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
        "value_provenance_required": "baseline_emitted_args",
        "schema_provenance_required": "dataset_tool_schema",
        "forbidden_fields_not_used": sorted(FORBIDDEN_KEYS),
        "default_or_example_value_source_used": False,
        "deterministic_local_conversion_only": True,
        "fuzzy_or_semantic_conversion": False,
        "postcondition_or_execution_feedback_used": False,
        "tool_choice_mutation": False,
        "trajectory_mutation": False,
        "unrelated_arg_mutation": False,
        "dataset_json": str(dataset_json),
        "source_manifest": str(source_manifest) if source_manifest else "default_tmp_batch1_batch2_roots",
        "requested_categories": requested_categories,
        "counters": {**counters, "reject_reason_counts": reject_reason_counts},
        "category_summaries": list(category_rows.values()),
        "eligible_schema_local_records": records[:25] if compact else records,
        "eligible_schema_local_record_count": len(records),
        "blockers": blockers,
        "schema_local_non_live_repair_diagnostic_passed": passed,
        "next_recommended_action": "research_review_required_do_not_lower_standards" if not records else "review_no_leakage_gate_before_any_candidate_pool_use",
    }
    _write_json(output_json, report)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_markdown(report), encoding="utf-8")
    return report


def _markdown(report: dict[str, Any]) -> str:
    c = report["counters"]
    keys = [
        "selected_call_count",
        "selected_calls_with_function_schema",
        "selected_calls_with_required_args",
        "required_args_present_count",
        "schema_local_checked_arg_count",
        "schema_local_type_mismatch_count",
        "numeric_string_to_integer_candidate_count",
        "numeric_string_to_number_candidate_count",
        "boolean_string_candidate_count",
        "enum_case_normalization_candidate_count",
        "singleton_array_wrap_candidate_count",
        "schema_local_candidate_count",
        "schema_local_repair_eligible_count",
        "schema_local_ambiguous_count",
        "schema_local_unsafe_conversion_count",
        "schema_local_noop_already_valid_count",
    ]
    lines = [
        "# Schema-Local Non-Live Repair Diagnostic",
        "",
        "This is an offline diagnostic artifact only. It is not candidate-pool, scorer, performance, or Huawei acceptance evidence.",
        "",
        f"- diagnostic_only: `{str(report['diagnostic_only']).lower()}`",
        f"- candidate_pool_authorized: `{str(report['candidate_pool_authorized']).lower()}`",
        f"- scorer_authorized: `{str(report['scorer_authorized']).lower()}`",
        f"- performance_evidence: `{str(report['performance_evidence']).lower()}`",
        f"- huawei_acceptance_ready: `{str(report['huawei_acceptance_ready']).lower()}`",
        f"- sota_3pp_claim_ready: `{str(report['sota_3pp_claim_ready']).lower()}`",
        "- value_provenance: `baseline_emitted_args`",
        "- schema_provenance: `dataset_tool_schema`",
        "- default_or_example_value_source_used: `false`",
        "- conversion rule: deterministic local conversion only; no fuzzy/semantic conversion",
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
        f"- next_recommended_action: `{report.get('next_recommended_action')}`",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline schema-local non-live repair diagnostic gate.")
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
        print(json.dumps({"passed": report["schema_local_non_live_repair_diagnostic_passed"], "counters": report["counters"], "blockers": report["blockers"]}, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["schema_local_non_live_repair_diagnostic_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
