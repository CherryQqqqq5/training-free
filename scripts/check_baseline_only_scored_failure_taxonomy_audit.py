#!/usr/bin/env python3
"""Baseline-only scored failure taxonomy audit for the raw-response pilot.

This audit reads existing baseline source outputs and scorer outputs only. It
never calls a provider/model, never runs a candidate, and never emits gold,
expected values, scorer diffs, or per-case repair recommendations.
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
    _schema_match,
    _selected_turn_calls,
    _tool_call_records,
)
from scripts.check_selected_call_structural_failure_attribution import (
    _extract_tool_like_payloads,
    _schema_matched_payloads,
    _schema_valid_args,
)

DEFAULT_RAW_ROOT = Path("/tmp/bfcl_source_collection_raw_response_capture")
DEFAULT_DATASET_JSON = Path("/tmp/explicit_literal_pool/explicit_literal_dataset.json")
DEFAULT_OUTPUT_JSON = Path("outputs/artifacts/stage1_bfcl_acceptance/baseline_only_scored_failure_taxonomy_audit.json")
DEFAULT_OUTPUT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/baseline_only_scored_failure_taxonomy_audit.md")
CURRENT_PROVIDER_ROUTE = "Chuangzhi/Novacode"
CURRENT_MODEL_ID = "gpt-5.2"
FORBIDDEN_EMIT_KEYS = {
    "gold", "expected", "answer", "ground_truth", "oracle", "score", "candidate",
    "repair", "reference", "possible_answer", "prompt", "model_result_raw",
    "model_result_decoded", "inference_log",
}


def _read_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    bad = 0
    if not path.exists():
        return rows, bad
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except Exception:
            bad += 1
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            bad += 1
    return rows, bad


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _raw_capture_records(raw_root: Path, categories: list[str]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for category in categories:
        path = raw_root / category / "baseline" / "raw_response_capture_records.jsonl"
        rows, _bad = _read_jsonl(path)
        for row in rows:
            cid = str(row.get("case_id") or row.get("id") or "")
            if cid:
                records[cid] = {**row, "category": str(row.get("category") or category)}
    return records


def _result_records(raw_root: Path, categories: list[str]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for category in categories:
        for path in sorted((raw_root / category / "baseline" / "bfcl" / "result").glob("*/multi_turn/*_result.json")):
            rows, _bad = _read_jsonl(path)
            for row in rows:
                cid = str(row.get("id") or row.get("case_id") or "")
                if cid:
                    records[cid] = row
    return records


def _score_rows(raw_root: Path, categories: list[str]) -> tuple[list[dict[str, Any]], int, int, list[str]]:
    detail: list[dict[str, Any]] = []
    bad = 0
    aggregate_total = 0
    files: list[str] = []
    for category in categories:
        for path in sorted((raw_root / category / "baseline" / "bfcl" / "score").glob("*/multi_turn/*_score.json")):
            files.append(str(path))
            rows, bad_rows = _read_jsonl(path)
            bad += bad_rows
            for row in rows:
                if "accuracy" in row and "correct_count" in row and "total_count" in row:
                    try:
                        aggregate_total += int(row.get("total_count") or 0)
                    except Exception:
                        pass
                    continue
                if row.get("id") or row.get("case_id"):
                    detail.append({**row, "_score_file_hash": _hash_text(str(path))})
    return detail, bad, aggregate_total, files


def _selected_schema_stats(entry: dict[str, Any] | None, result_row: dict[str, Any] | None) -> tuple[int, int, int, bool]:
    if not entry or not result_row:
        return 0, 0, 0, False
    calls = _tool_call_records(result_row.get("result"))
    _historical, selected = _selected_turn_calls(calls)
    matched = 0
    valid = 0
    for call in selected:
        fn, status, _reason, _names = _schema_match(entry, str(call.get("tool") or ""))
        if status == "matched" and fn:
            matched += 1
            if _schema_valid_args(fn, call.get("args") or {}):
                valid += 1
    return len(selected), matched, valid, bool(selected)


def _classify_failure(*, entry: dict[str, Any] | None, capture: dict[str, Any] | None, result_row: dict[str, Any] | None, score_row: dict[str, Any]) -> str:
    raw = capture.get("raw_response") if capture else None
    if raw is None and capture:
        raw = capture.get("raw_response_text")
    payloads, malformed, _final_text, _meta = _extract_tool_like_payloads(raw) if raw is not None else ([], False, False, {})
    selected_count, selected_schema, selected_valid, selected_present = _selected_schema_stats(entry, result_row)
    error = score_row.get("error") if isinstance(score_row.get("error"), dict) else {}
    error_type = str(error.get("error_type") or "")
    if not payloads:
        return "failure_with_no_tool_like_payload"
    if entry and payloads and not _schema_matched_payloads(entry, payloads):
        return "failure_with_raw_payload_schema_not_matched"
    if selected_present and selected_schema == 0:
        return "failure_with_selected_schema_not_matched"
    if "empty_turn" in error_type or (not selected_present and payloads):
        return "failure_with_extra_or_missing_call_count"
    if "argument_name" in error_type or "parameter_name" in error_type:
        return "failure_with_argument_name_mismatch"
    if "argument_value" in error_type or "parameter_value" in error_type:
        return "failure_with_argument_value_mismatch"
    if "wrong_tool" in error_type or "order" in error_type:
        return "failure_with_wrong_tool_or_order"
    if "execution" in error_type or "state_mismatch" in error_type:
        return "failure_with_schema_valid_selected_calls" if selected_valid else "failure_with_execution_or_state_mismatch"
    if selected_valid:
        return "failure_with_schema_valid_selected_calls"
    return "unattributed_failure_count"


def build_report(
    *,
    raw_root: Path = DEFAULT_RAW_ROOT,
    dataset_json: Path = DEFAULT_DATASET_JSON,
    categories: str | list[str] = "multi_turn_miss_func,multi_turn_base,multi_turn_long_context",
    output_json: Path = DEFAULT_OUTPUT_JSON,
    markdown_output: Path = DEFAULT_OUTPUT_MD,
) -> dict[str, Any]:
    category_list = [c.strip() for c in categories.split(",") if c.strip()] if isinstance(categories, str) else list(categories)
    dataset = _dataset_records(dataset_json) if dataset_json.exists() else {}
    captures = _raw_capture_records(raw_root, category_list)
    results = _result_records(raw_root, category_list)
    score_detail_rows, bad_score_rows, aggregate_total, score_files = _score_rows(raw_root, category_list)
    audited_case_ids = set(captures)
    scored_case_ids = {str(row.get("case_id") or row.get("id")) for row in score_detail_rows if row.get("case_id") or row.get("id")}
    source_score_overlap = audited_case_ids & scored_case_ids

    counters: dict[str, Any] = {
        "audited_case_count": len(audited_case_ids),
        "scored_case_count": aggregate_total or len(scored_case_ids),
        "source_score_case_overlap_count": len(source_score_overlap),
        "missing_score_count": max(0, len(audited_case_ids) - (aggregate_total or len(scored_case_ids))),
        "bad_score_rows": bad_score_rows,
        "route_model_matched_count": 0,
        "forbidden_field_violation_count": 0,
        "baseline_success_count": 0,
        "baseline_failure_count": 0,
        "baseline_success_rate": 0.0,
        "baseline_failure_rate": 0.0,
        "failure_with_no_tool_like_payload": 0,
        "failure_with_raw_payload_schema_not_matched": 0,
        "failure_with_selected_schema_not_matched": 0,
        "failure_with_schema_valid_selected_calls": 0,
        "failure_with_wrong_tool_or_order": 0,
        "failure_with_extra_or_missing_call_count": 0,
        "failure_with_argument_name_mismatch": 0,
        "failure_with_argument_value_mismatch": 0,
        "failure_with_execution_or_state_mismatch": 0,
        "unattributed_failure_count": 0,
    }
    raw_score_gold_bearing_rows_read_count = 0
    failure_bucket_hashes: dict[str, list[str]] = {key: [] for key in counters if str(key).startswith("failure_with_") or key == "unattributed_failure_count"}
    route_model_matched_ids: set[str] = set()
    failures = 0
    for row in score_detail_rows:
        cid = str(row.get("case_id") or row.get("id") or "")
        if not cid:
            continue
        if any(key in row for key in FORBIDDEN_EMIT_KEYS):
            raw_score_gold_bearing_rows_read_count += 1
        capture = captures.get(cid)
        if capture and capture.get("provider_route") == CURRENT_PROVIDER_ROUTE and capture.get("model_id") == CURRENT_MODEL_ID:
            route_model_matched_ids.add(cid)
        if row.get("valid") is True:
            continue
        failures += 1
        bucket = _classify_failure(entry=dataset.get(cid), capture=capture, result_row=results.get(cid), score_row=row)
        counters[bucket] += 1
        failure_bucket_hashes.setdefault(bucket, []).append(_hash_text(cid))
    counters["route_model_matched_count"] = len(route_model_matched_ids)
    counters["baseline_failure_count"] = failures
    counters["baseline_success_count"] = max(0, int(counters["scored_case_count"]) - failures)
    if counters["scored_case_count"]:
        counters["baseline_success_rate"] = round(counters["baseline_success_count"] / counters["scored_case_count"], 6)
        counters["baseline_failure_rate"] = round(counters["baseline_failure_count"] / counters["scored_case_count"], 6)

    report = {
        "report_scope": "baseline_only_scored_failure_taxonomy_audit",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "server_path": "/cephfs/qiuyn/training-free",
        "branch": "stage1-bfcl-performance-sprint",
        "raw_root": str(raw_root),
        "dataset_json": str(dataset_json),
        "audit_only": True,
        "baseline_only": True,
        "candidate_extraction_authorized": False,
        "candidate_pool_authorized": False,
        "scorer_authorization_for_performance": False,
        "candidate_run_authorized": False,
        "paired_comparison_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "no_leakage_to_candidate_pool": True,
        "gold_text_emitted": False,
        "expected_values_emitted": False,
        "per_case_repair_recommendations_emitted": False,
        "does_not_run_provider_or_model_generation": True,
        "does_not_run_candidate_paired_dev_holdout_full": True,
        "uses_existing_offline_score_outputs_only": True,
        "raw_scorer_files_remain_untracked": True,
        "tracked_artifact_contains_aggregate_buckets_and_hashes_only": True,
        "categories": category_list,
        "score_file_count": len(score_files),
        "score_file_hashes": [_hash_text(path) for path in score_files],
        "current_route_model_scope": {"provider_route": CURRENT_PROVIDER_ROUTE, "model": CURRENT_MODEL_ID},
        "raw_score_gold_bearing_rows_read_count": raw_score_gold_bearing_rows_read_count,
        "counters": counters,
        "aggregate_bucket_sample_hashes": {key: values[:5] for key, values in sorted(failure_bucket_hashes.items()) if values},
        "decision": {
            "taxonomy_audit_completed": True,
            "performance_evidence": False,
            "candidate_pool_action": "none",
            "next_action": "research_review_only_do_not_expand_or_promote_candidate_pool",
        },
    }
    _write_json(output_json, report)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(_markdown(report), encoding="utf-8")
    return report


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _markdown(report: dict[str, Any]) -> str:
    c = report["counters"]
    keys = [
        "audited_case_count", "scored_case_count", "source_score_case_overlap_count", "missing_score_count",
        "bad_score_rows", "route_model_matched_count", "forbidden_field_violation_count",
        "baseline_success_count", "baseline_failure_count", "baseline_success_rate", "baseline_failure_rate",
        "failure_with_no_tool_like_payload", "failure_with_raw_payload_schema_not_matched",
        "failure_with_selected_schema_not_matched", "failure_with_schema_valid_selected_calls",
        "failure_with_wrong_tool_or_order", "failure_with_extra_or_missing_call_count",
        "failure_with_argument_name_mismatch", "failure_with_argument_value_mismatch",
        "failure_with_execution_or_state_mismatch", "unattributed_failure_count",
    ]
    lines = [
        "# Baseline-Only Scored Failure Taxonomy Audit", "",
        "This is scorer-output taxonomy only. It is not performance evidence and does not authorize candidate extraction, candidate pool promotion, paired comparison, dev/holdout/full scoring, or provider/model generation.", "",
        "## Flags", "",
        f"- audit_only: `{str(report['audit_only']).lower()}`",
        f"- baseline_only: `{str(report['baseline_only']).lower()}`",
        f"- candidate_extraction_authorized: `{str(report['candidate_extraction_authorized']).lower()}`",
        f"- candidate_pool_authorized: `{str(report['candidate_pool_authorized']).lower()}`",
        f"- scorer_authorization_for_performance: `{str(report['scorer_authorization_for_performance']).lower()}`",
        f"- performance_evidence: `{str(report['performance_evidence']).lower()}`",
        f"- sota_3pp_claim_ready: `{str(report['sota_3pp_claim_ready']).lower()}`",
        f"- huawei_acceptance_ready: `{str(report['huawei_acceptance_ready']).lower()}`", "",
        "## Counters", "", "| counter | value |", "| --- | ---: |",
    ]
    for key in keys:
        val = c.get(key, 0)
        lines.append(f"| {key} | {val} |")
    lines += [
        "", "## Notes", "",
        f"- score_file_count: `{report.get('score_file_count')}`",
        f"- raw_score_gold_bearing_rows_read_count: `{report.get('raw_score_gold_bearing_rows_read_count')}`; raw scorer rows were read only under aggregate-taxonomy authorization and no gold/expected content was emitted.",
        "- aggregate_bucket_sample_hashes contain case-id hashes only, not case text, gold, expected values, scorer diffs, or repair recommendations.",
        f"- next_action: `{report['decision']['next_action']}`",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Baseline-only scored failure taxonomy audit over raw-response pilot outputs.")
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--dataset-json", type=Path, default=DEFAULT_DATASET_JSON)
    parser.add_argument("--categories", default="multi_turn_miss_func,multi_turn_base,multi_turn_long_context")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = build_report(raw_root=args.raw_root, dataset_json=args.dataset_json, categories=args.categories, output_json=args.output, markdown_output=args.markdown_output)
    if args.compact:
        print(json.dumps({"counters": report["counters"], "decision": report["decision"]}, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
