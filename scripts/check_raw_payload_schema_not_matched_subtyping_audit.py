#!/usr/bin/env python3
"""Offline subtyping audit for raw-payload schema-not-matched failures.

The audit is restricted to the baseline-only taxonomy bucket
`failure_with_raw_payload_schema_not_matched`. It reads existing raw-response
pilot records, baseline result rows, dataset schemas, and score rows only to
identify bucket membership. It never calls provider/scorer/source collection and
never emits gold/expected/scorer diff or per-case repair recommendations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from scripts.build_explicit_literal_candidate_pool import _dataset_records
from scripts.check_baseline_only_scored_failure_taxonomy_audit import (
    _classify_failure,
    _raw_capture_records,
    _result_records,
    _score_rows,
)
from scripts.check_selected_call_structural_failure_attribution import _extract_tool_like_payloads

DEFAULT_RAW_ROOT = Path("/tmp/bfcl_source_collection_raw_response_capture")
DEFAULT_DATASET_JSON = Path("/tmp/explicit_literal_pool/explicit_literal_dataset.json")
DEFAULT_OUTPUT_JSON = Path("outputs/artifacts/stage1_bfcl_acceptance/raw_payload_schema_not_matched_subtyping_audit.json")
DEFAULT_OUTPUT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/raw_payload_schema_not_matched_subtyping_audit.md")
TARGET_BUCKET = "failure_with_raw_payload_schema_not_matched"


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _function_names(entry: dict[str, Any] | None) -> list[str]:
    if not isinstance(entry, dict):
        return []
    funcs = entry.get("function") or entry.get("functions") or entry.get("tools") or []
    names: list[str] = []
    if isinstance(funcs, dict):
        funcs = [funcs]
    if isinstance(funcs, list):
        for fn in funcs:
            if isinstance(fn, dict):
                name = fn.get("name") or fn.get("function", {}).get("name") if isinstance(fn.get("function"), dict) else fn.get("name")
                if name:
                    names.append(str(name))
    return sorted(set(names))


def _entry_paths(entry: dict[str, Any] | None) -> list[str]:
    if not isinstance(entry, dict):
        return []
    vals: list[str] = []
    for key in ("path", "involved_classes", "involved_classes_path", "class_path"):
        value = entry.get(key)
        if isinstance(value, str):
            vals.append(value)
        elif isinstance(value, list):
            vals.extend(str(item) for item in value if isinstance(item, (str, int, float)))
    return vals


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _separator_norm(value: str) -> str:
    return re.sub(r"[._\-/\\:]+", "", value.lower())


def _short(value: str) -> str:
    return re.split(r"[._\-/\\:]+", value)[-1]


def _unique_match(candidates: list[str], schema_names: list[str]) -> str | None:
    unique = sorted({name for name in candidates if name in schema_names})
    return unique[0] if len(unique) == 1 else None


def _unique_by_key(tool: str, schema_names: list[str], key_fn) -> tuple[str | None, bool]:  # type: ignore[no-untyped-def]
    key = key_fn(tool)
    matches = sorted({name for name in schema_names if key_fn(name) == key})
    if len(matches) == 1:
        return matches[0], False
    return None, len(matches) > 1


def _classify_tool_name(tool: str, entry: dict[str, Any] | None) -> tuple[str, bool, bool]:
    schema_names = _function_names(entry)
    if not schema_names:
        return "no_schema_name_candidate", False, False
    if tool in schema_names:
        return "exact_schema_match_unexpected", False, False
    lower_matches = sorted({name for name in schema_names if name.lower() == tool.lower()})
    if len(lower_matches) == 1:
        return "case_insensitive_unique_match", True, False
    if len(lower_matches) > 1:
        return "multiple_schema_name_candidates", False, True
    matched, ambiguous = _unique_by_key(tool, schema_names, _separator_norm)
    if matched:
        return "punctuation_or_separator_unique_match", True, False
    if ambiguous:
        return "multiple_schema_name_candidates", False, True
    short_tool = _short(tool)
    short_matches = sorted({name for name in schema_names if name == short_tool or _short(name) == short_tool})
    if len(short_matches) == 1:
        if any(sep in tool for sep in ("/", "\\", ":")):
            return "provider_namespace_or_path_alias_unique_match", True, False
        return "qualified_short_name_unique_match", True, False
    if len(short_matches) > 1:
        return "multiple_schema_name_candidates", False, True
    norm_matches = sorted({name for name in schema_names if _norm(name) == _norm(tool)})
    if len(norm_matches) == 1:
        return "emitted_tool_name_normalized_unique_match", True, False
    if len(norm_matches) > 1:
        return "multiple_schema_name_candidates", False, True
    path_candidates = _entry_paths(entry)
    if path_candidates:
        path_matches = sorted({name for name in schema_names if any(_short(str(path)) == name or _norm(str(path)) == _norm(name) for path in path_candidates)})
        if len(path_matches) == 1 and (_norm(path_matches[0]) == _norm(tool) or _short(tool) == path_matches[0]):
            return "involved_class_or_path_unique_match", True, False
        if len(path_matches) > 1:
            return "multiple_schema_name_candidates", False, True
    return "no_schema_name_candidate", False, False


def _score_bucket_cases(raw_root: Path, dataset: dict[str, dict[str, Any]], categories: list[str]) -> tuple[list[str], dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    captures = _raw_capture_records(raw_root, categories)
    results = _result_records(raw_root, categories)
    score_rows, _bad, _aggregate_total, _files = _score_rows(raw_root, categories)
    cases: list[str] = []
    for row in score_rows:
        cid = str(row.get("case_id") or row.get("id") or "")
        if not cid or row.get("valid") is True:
            continue
        bucket = _classify_failure(entry=dataset.get(cid), capture=captures.get(cid), result_row=results.get(cid), score_row=row)
        if bucket == TARGET_BUCKET:
            cases.append(cid)
    return sorted(set(cases)), captures, results, {str(row.get("case_id") or row.get("id")): row for row in score_rows if row.get("case_id") or row.get("id")}


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
    target_cases, captures, _results, _scores = _score_bucket_cases(raw_root, dataset, category_list)
    counters: dict[str, int] = {
        "raw_payload_schema_not_matched_failure_count": len(target_cases),
        "input_case_count": len(target_cases),
        "audited_bucket_case_count": 0,
        "raw_response_present_count": 0,
        "dataset_schema_present_count": 0,
        "forbidden_field_violation_count": 0,
        "emitted_tool_name_exact_schema_miss_count": 0,
        "emitted_tool_name_normalized_unique_match_count": 0,
        "case_insensitive_unique_match_count": 0,
        "punctuation_or_separator_unique_match_count": 0,
        "provider_namespace_or_path_alias_unique_match_count": 0,
        "qualified_short_name_unique_match_count": 0,
        "involved_class_or_path_unique_match_count": 0,
        "multiple_schema_name_candidates_count": 0,
        "no_schema_name_candidate_count": 0,
        "requires_gold_tool_identity_count": 0,
        "tool_selection_semantic_mismatch_count": 0,
        "unattributed_schema_not_matched_count": 0,
        "normalization_uses_gold_count": 0,
        "normalization_changes_arguments_count": 0,
        "normalization_changes_tool_order_count": 0,
        "normalization_changes_call_count": 0,
        "ambiguous_normalization_reject_count": 0,
        "deterministic_source_schema_only_possible_count": 0,
    }
    subtype_hashes: dict[str, list[str]] = {}
    for cid in target_cases:
        counters["audited_bucket_case_count"] += 1
        capture = captures.get(cid) or {}
        raw = capture.get("raw_response") if isinstance(capture, dict) else None
        if raw is None and isinstance(capture, dict):
            raw = capture.get("raw_response_text")
        if raw is not None:
            counters["raw_response_present_count"] += 1
        entry = dataset.get(cid)
        if _function_names(entry):
            counters["dataset_schema_present_count"] += 1
        payloads, _malformed, _final_text, _meta = _extract_tool_like_payloads(raw) if raw is not None else ([], False, False, {})
        exact_miss_for_case = False
        case_subtypes: list[str] = []
        deterministic = False
        ambiguous = False
        if not payloads:
            counters["unattributed_schema_not_matched_count"] += 1
            case_subtypes.append("unattributed_schema_not_matched")
        for payload in payloads:
            tool = str(payload.get("tool") or "")
            schema_names = _function_names(entry)
            if schema_names and tool not in schema_names:
                exact_miss_for_case = True
            subtype, is_deterministic, is_ambiguous = _classify_tool_name(tool, entry)
            if subtype == "exact_schema_match_unexpected":
                continue
            counter = subtype + "_count" if not subtype.endswith("_count") else subtype
            if counter in counters:
                counters[counter] += 1
            else:
                counters["unattributed_schema_not_matched_count"] += 1
            case_subtypes.append(subtype)
            deterministic = deterministic or is_deterministic
            ambiguous = ambiguous or is_ambiguous
        if exact_miss_for_case:
            counters["emitted_tool_name_exact_schema_miss_count"] += 1
        if ambiguous:
            counters["ambiguous_normalization_reject_count"] += 1
        if deterministic and not ambiguous:
            counters["deterministic_source_schema_only_possible_count"] += 1
        elif not deterministic and not ambiguous and payloads:
            counters["tool_selection_semantic_mismatch_count"] += 1
        for subtype in sorted(set(case_subtypes)):
            subtype_hashes.setdefault(subtype, []).append(_hash_text(cid))
    decision = {
        "recommendation": "separate_approval_packet_only_do_not_generate_candidates" if counters["deterministic_source_schema_only_possible_count"] >= 3 else "stop_no_yield_research_review",
        "candidate_generation_authorized": False,
        "candidate_pool_action": "none",
        "performance_evidence": False,
    }
    report = {
        "report_scope": "raw_payload_schema_not_matched_subtyping_audit",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "server_path": "/cephfs/qiuyn/training-free",
        "branch": "stage1-bfcl-performance-sprint",
        "raw_root": str(raw_root),
        "dataset_json": str(dataset_json),
        "source_bucket": TARGET_BUCKET,
        "audit_only": True,
        "offline_only": True,
        "candidate_extraction_authorized": False,
        "candidate_pool_authorized": False,
        "scorer_authorization_for_performance": False,
        "provider_run_authorized": False,
        "source_collection_authorized": False,
        "candidate_run_authorized": False,
        "paired_comparison_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "gold_text_emitted": False,
        "expected_values_emitted": False,
        "per_case_repair_recommendations_emitted": False,
        "no_leakage_to_candidate_pool": True,
        "normalization_source": "dataset_schema_and_emitted_tool_name_only",
        "does_not_use_gold_tool_identity_or_values": True,
        "does_not_change_arguments_tool_order_or_call_count": True,
        "tracked_artifact_contains_counters_and_hashes_only": True,
        "counters": counters,
        "subtype_case_hashes": {key: values[:5] for key, values in sorted(subtype_hashes.items())},
        "decision": decision,
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
        "raw_payload_schema_not_matched_failure_count", "input_case_count", "audited_bucket_case_count",
        "raw_response_present_count", "dataset_schema_present_count", "forbidden_field_violation_count",
        "emitted_tool_name_exact_schema_miss_count", "emitted_tool_name_normalized_unique_match_count",
        "case_insensitive_unique_match_count", "punctuation_or_separator_unique_match_count",
        "provider_namespace_or_path_alias_unique_match_count", "qualified_short_name_unique_match_count",
        "involved_class_or_path_unique_match_count", "multiple_schema_name_candidates_count",
        "no_schema_name_candidate_count", "requires_gold_tool_identity_count", "tool_selection_semantic_mismatch_count",
        "unattributed_schema_not_matched_count", "normalization_uses_gold_count",
        "normalization_changes_arguments_count", "normalization_changes_tool_order_count",
        "normalization_changes_call_count", "ambiguous_normalization_reject_count",
        "deterministic_source_schema_only_possible_count",
    ]
    lines = [
        "# Raw Payload Schema-Not-Matched Subtyping Audit", "",
        "Offline audit over the `failure_with_raw_payload_schema_not_matched` bucket only. It is not candidate extraction, not performance evidence, and not scorer/provider/source collection execution.", "",
        "## Flags", "",
    ]
    for key in ["audit_only", "offline_only", "candidate_extraction_authorized", "candidate_pool_authorized", "scorer_authorization_for_performance", "provider_run_authorized", "source_collection_authorized", "candidate_run_authorized", "paired_comparison_authorized", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "gold_text_emitted", "expected_values_emitted", "per_case_repair_recommendations_emitted", "no_leakage_to_candidate_pool"]:
        lines.append(f"- {key}: `{str(report[key]).lower()}`")
    lines += ["", "## Counters", "", "| counter | value |", "| --- | ---: |"]
    for key in keys:
        lines.append(f"| {key} | {c.get(key, 0)} |")
    lines += ["", "## Decision", "", f"- recommendation: `{report['decision']['recommendation']}`", "- no candidates were generated or authorized"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline subtyping audit for raw-payload schema-not-matched failures.")
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
