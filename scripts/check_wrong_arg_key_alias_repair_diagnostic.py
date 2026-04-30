#!/usr/bin/env python3
"""Offline diagnostic gate for wrong-argument-key alias repair.

This script scans existing BFCL source-collection result JSONL and sanitized
dataset schema only. It does not call a provider, BFCL, a model, or a scorer,
and it does not emit candidate-pool rules. The only eligible diagnostic pattern
is a deterministic key-normalization alias where the canonical required schema
argument is absent, exactly one emitted argument key normalizes to it, and the
emitted value is schema-compatible.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from scripts.build_explicit_literal_candidate_pool import (
    _dataset_records,
    _missing_required_args,
    _normalize_identifier,
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
DEFAULT_OUTPUT_JSON = Path("outputs/artifacts/stage1_bfcl_acceptance/wrong_arg_key_alias_repair_diagnostic.json")
DEFAULT_OUTPUT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/wrong_arg_key_alias_repair_diagnostic.md")
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


def _schema_for_arg(fn: dict[str, Any], arg: str) -> dict[str, Any]:
    schema = _properties(fn).get(arg)
    return schema if isinstance(schema, dict) else {}


def _value_schema_compatible(value: Any, schema: dict[str, Any]) -> bool:
    expected = str(schema.get("type") or "").lower()
    if expected in {"", "string"}:
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return False


def _default_source_manifest() -> dict[str, Any]:
    roots = []
    for category in ("multi_turn_miss_func", "multi_turn_base", "multi_turn_long_context"):
        root = Path(f"/tmp/bfcl_source_collection/{category}/baseline")
        if root.exists():
            roots.append({"category": category, "existing_source_roots": [str(root)]})
    return {"category_status": roots}


def _empty_category(category: str) -> dict[str, Any]:
    return {
        "category": category,
        "result_jsonl_rows": 0,
        "selected_call_count": 0,
        "alias_repair_eligible_count": 0,
        "reject_reason_counts": {},
    }


def _diagnose_call(
    *,
    case_id: str,
    category: str,
    call: dict[str, Any],
    fn: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    rows: list[dict[str, Any]] = []
    reject_reasons: list[str] = []
    counters = {
        "required_arg_absent_by_canonical_key_count": 0,
        "emitted_alias_key_present_count": 0,
        "alias_map_unique_count": 0,
        "alias_value_schema_compatible_count": 0,
        "wrong_key_alias_candidate_count": 0,
        "alias_ambiguous_count": 0,
        "alias_type_mismatch_count": 0,
        "alias_repair_eligible_count": 0,
    }
    args = call.get("args") or {}
    if not isinstance(args, dict):
        reject_reasons.append("emitted_args_not_object")
        return rows, reject_reasons, counters

    emitted_by_norm: dict[str, list[str]] = {}
    for key in args:
        emitted_by_norm.setdefault(_normalize_identifier(str(key)), []).append(str(key))

    for required_arg in _required_args(fn):
        if required_arg in args:
            reject_reasons.append("canonical_arg_already_present")
            continue
        counters["required_arg_absent_by_canonical_key_count"] += 1
        normalized_required = _normalize_identifier(required_arg)
        alias_keys = [key for key in emitted_by_norm.get(normalized_required, []) if key != required_arg]
        if not alias_keys:
            reject_reasons.append("alias_key_not_present")
            continue
        counters["emitted_alias_key_present_count"] += 1
        if len(alias_keys) != 1:
            counters["alias_ambiguous_count"] += 1
            reject_reasons.append("alias_key_not_unique")
            continue
        alias_key = alias_keys[0]
        counters["alias_map_unique_count"] += 1
        value = args.get(alias_key)
        if not _value_schema_compatible(value, _schema_for_arg(fn, required_arg)):
            counters["alias_type_mismatch_count"] += 1
            reject_reasons.append("alias_type_mismatch")
            continue
        counters["alias_value_schema_compatible_count"] += 1
        counters["wrong_key_alias_candidate_count"] += 1
        counters["alias_repair_eligible_count"] += 1
        rows.append({
            "case_id": case_id,
            "category": category,
            "diagnostic_only": True,
            "source_value_provenance": "baseline_emitted_args",
            "function": str(fn.get("name") or call.get("tool")),
            "emitted_tool": str(call.get("tool")),
            "canonical_arg": required_arg,
            "emitted_alias_key": alias_key,
            "alias_rule": "normalize_identifier_exact_match",
            "turn_index": call.get("turn_index"),
            "step_index": call.get("step_index"),
            "call_index": call.get("call_index"),
            "tool_choice_mutation": False,
            "trajectory_mutation": False,
            "canonical_arg_overwrite": False,
        })
    return rows, reject_reasons, counters


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
        "required_arg_absent_by_canonical_key_count": 0,
        "emitted_alias_key_present_count": 0,
        "alias_map_unique_count": 0,
        "alias_value_schema_compatible_count": 0,
        "wrong_key_alias_candidate_count": 0,
        "alias_ambiguous_count": 0,
        "alias_type_mismatch_count": 0,
        "alias_repair_eligible_count": 0,
    }
    reject_reason_counts: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    blockers: list[str] = []
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
        result_rows = _result_rows(result_path)
        bucket["result_jsonl_rows"] += len(result_rows)
        if result_path is None:
            reject("missing_source_result", category)
            continue
        for row in result_rows:
            case_id = str(row.get("id") or row.get("case_id") or "")
            entry = dataset.get(case_id)
            if not entry:
                reject("dataset_record_missing", category)
                continue
            row_metadata = {key: value for key, value in row.items() if key != "result"}
            if _contains_forbidden_key(entry) or _contains_forbidden_key(row_metadata):
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
                if _required_args(fn):
                    counters["selected_calls_with_required_args"] += 1
                else:
                    reject("schema_required_empty", category)
                    continue
                _missing, arg_conflicts, _present = _missing_required_args(fn, call.get("args") or {})
                if arg_conflicts:
                    counters["alias_ambiguous_count"] += 1
                    reject("arg_key_conflict", category)
                    continue
                diag_rows, reasons, local = _diagnose_call(case_id=case_id, category=category, call=call, fn=fn)
                for key, value in local.items():
                    counters[key] += value
                rows.extend(diag_rows)
                bucket["alias_repair_eligible_count"] += local["alias_repair_eligible_count"]
                if not diag_rows:
                    for reason in sorted(set(reasons)):
                        reject(reason, category)

    if not rows:
        blockers.append("wrong_arg_key_alias_repair_eligible_count_zero")
    passed = bool(rows) and not blockers
    report = {
        "report_scope": "wrong_arg_key_alias_repair_diagnostic",
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
        "source_value_provenance_required": "baseline_emitted_args",
        "forbidden_fields_not_used": sorted(FORBIDDEN_KEYS),
        "deterministic_alias_map_only": True,
        "fuzzy_or_semantic_aliasing": False,
        "tool_choice_mutation": False,
        "trajectory_mutation": False,
        "existing_canonical_arg_overwrite": False,
        "rejected_records_enter_candidate_pool": False,
        "dataset_json": str(dataset_json),
        "source_manifest": str(source_manifest) if source_manifest else "default_tmp_batch1_batch2_roots",
        "requested_categories": requested_categories,
        "counters": {**counters, "reject_reason_counts": reject_reason_counts},
        "category_summaries": list(category_rows.values()),
        "eligible_alias_records": rows[:25] if compact else rows,
        "eligible_alias_record_count": len(rows),
        "blockers": blockers,
        "wrong_arg_key_alias_repair_diagnostic_passed": passed,
        "next_recommended_diagnostic": "deterministic_schema_local_non_live_repair" if not rows else "review_no_leakage_gate_before_any_candidate_pool_use",
    }
    _write_json(output_json, report)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_markdown(report), encoding="utf-8")
    return report


def _markdown(report: dict[str, Any]) -> str:
    c = report["counters"]
    lines = [
        "# Wrong Arg Key Alias Repair Diagnostic",
        "",
        "This is an offline diagnostic artifact only. It is not candidate-pool, scorer, performance, or Huawei acceptance evidence.",
        "",
        f"- diagnostic_only: `{str(report['diagnostic_only']).lower()}`",
        f"- candidate_pool_authorized: `{str(report['candidate_pool_authorized']).lower()}`",
        f"- scorer_authorized: `{str(report['scorer_authorized']).lower()}`",
        f"- performance_evidence: `{str(report['performance_evidence']).lower()}`",
        f"- huawei_acceptance_ready: `{str(report['huawei_acceptance_ready']).lower()}`",
        f"- sota_3pp_claim_ready: `{str(report['sota_3pp_claim_ready']).lower()}`",
        "- source_value_provenance: `baseline_emitted_args`",
        "- alias rule: deterministic `normalize_identifier_exact_match`; no fuzzy/semantic aliasing",
        "",
        "## Counters",
        "",
        "| counter | value |",
        "| --- | ---: |",
    ]
    for key in [
        "selected_call_count",
        "selected_calls_with_function_schema",
        "selected_calls_with_required_args",
        "required_arg_absent_by_canonical_key_count",
        "emitted_alias_key_present_count",
        "alias_map_unique_count",
        "alias_value_schema_compatible_count",
        "wrong_key_alias_candidate_count",
        "alias_ambiguous_count",
        "alias_type_mismatch_count",
        "alias_repair_eligible_count",
    ]:
        lines.append(f"| {key} | {c.get(key, 0)} |")
    lines.extend([
        "",
        f"- reject_reason_counts: `{json.dumps(c.get('reject_reason_counts', {}), sort_keys=True)}`",
        f"- blockers: `{json.dumps(report.get('blockers', []), sort_keys=True)}`",
        f"- next_recommended_diagnostic: `{report.get('next_recommended_diagnostic')}`",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline wrong-arg-key alias repair diagnostic gate.")
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
        print(json.dumps({"passed": report["wrong_arg_key_alias_repair_diagnostic_passed"], "counters": report["counters"], "blockers": report["blockers"]}, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["wrong_arg_key_alias_repair_diagnostic_passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
