#!/usr/bin/env python3
"""Offline schema retrieval/rerank feasibility diagnostic.

This diagnostic is restricted to the `raw_payload_schema_not_matched` failure
bucket. It uses deterministic lexical overlap between existing raw emitted tool
calls, current prompt text, emitted argument keys, and dataset schema metadata.
It never calls provider/scorer/source collection and never uses gold/scorer diff
as a rerank target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

from scripts.build_explicit_literal_candidate_pool import _dataset_records, _properties
from scripts.check_raw_payload_schema_not_matched_subtyping_audit import _score_bucket_cases
from scripts.check_selected_call_structural_failure_attribution import _extract_tool_like_payloads

DEFAULT_RAW_ROOT = Path("/tmp/bfcl_source_collection_raw_response_capture")
DEFAULT_DATASET_JSON = Path("/tmp/explicit_literal_pool/explicit_literal_dataset.json")
DEFAULT_OUTPUT_JSON = Path("outputs/artifacts/stage1_bfcl_acceptance/schema_retrieval_rerank_feasibility_diagnostic.json")
DEFAULT_OUTPUT_MD = Path("outputs/artifacts/stage1_bfcl_acceptance/schema_retrieval_rerank_feasibility_diagnostic.md")
INPUT_BUCKET = "raw_payload_schema_not_matched"
HIGH_MARGIN_THRESHOLD = 2
MIN_TOP_SCORE = 3


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _tokens(value: Any) -> set[str]:
    if value is None:
        return set()
    text = json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else str(value)
    parts = re.findall(r"[A-Za-z][A-Za-z0-9]*|[0-9]+", text)
    out: set[str] = set()
    for part in parts:
        out.add(part.lower())
        split = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", part)
        out.update(tok.lower() for tok in re.findall(r"[A-Za-z][A-Za-z0-9]*|[0-9]+", split))
    return {tok for tok in out if len(tok) > 1}


def _schema_functions(entry: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(entry, dict):
        return []
    funcs = entry.get("function") or entry.get("functions") or entry.get("tools") or []
    if isinstance(funcs, dict):
        funcs = [funcs]
    result = []
    if isinstance(funcs, list):
        for fn in funcs:
            if not isinstance(fn, dict):
                continue
            if isinstance(fn.get("function"), dict):
                fn = fn["function"]
            if fn.get("name"):
                result.append(fn)
    return result


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


def _prompt_text(entry: dict[str, Any] | None) -> str:
    if not isinstance(entry, dict):
        return ""
    chunks: list[str] = []
    for key in ("question", "messages"):
        value = entry.get(key)
        if value is not None:
            chunks.append(json.dumps(value, ensure_ascii=False, sort_keys=True))
    return "\n".join(chunks)


def _raw_payloads(capture: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(capture, dict):
        return []
    raw = capture.get("raw_response") if capture.get("raw_response") is not None else capture.get("raw_response_text")
    payloads, _malformed, _final_text, _meta = _extract_tool_like_payloads(raw) if raw is not None else ([], False, False, {})
    return payloads


def _score_schema(fn: dict[str, Any], *, raw_tool_tokens: set[str], prompt_tokens: set[str], arg_key_tokens: set[str], path_tokens: set[str]) -> dict[str, Any]:
    name = str(fn.get("name") or "")
    props = _properties(fn)
    name_tokens = _tokens(name)
    param_tokens = set()
    for key in props:
        param_tokens.update(_tokens(key))
    schema_tokens = name_tokens | param_tokens
    raw_overlap = raw_tool_tokens & name_tokens
    prompt_overlap = prompt_tokens & schema_tokens
    param_overlap = arg_key_tokens & param_tokens
    path_overlap = path_tokens & name_tokens
    score = 3 * len(raw_overlap) + len(prompt_overlap) + 2 * len(param_overlap) + len(path_overlap)
    return {
        "name_hash": _hash_text(name),
        "score": score,
        "raw_support": bool(raw_overlap),
        "prompt_support": bool(prompt_overlap),
        "parameter_support": bool(param_overlap),
        "class_or_path_support": bool(path_overlap),
    }


def _case_rerank(entry: dict[str, Any] | None, capture: dict[str, Any] | None) -> dict[str, Any]:
    funcs = _schema_functions(entry)
    payloads = _raw_payloads(capture)
    raw_tool_tokens: set[str] = set()
    arg_key_tokens: set[str] = set()
    for payload in payloads:
        raw_tool_tokens.update(_tokens(payload.get("tool")))
        args = payload.get("args") if isinstance(payload.get("args"), dict) else {}
        for key in args:
            arg_key_tokens.update(_tokens(key))
    prompt = _prompt_text(entry)
    prompt_tokens = _tokens(prompt)
    path_tokens = _tokens(_entry_paths(entry))
    scored = [_score_schema(fn, raw_tool_tokens=raw_tool_tokens, prompt_tokens=prompt_tokens, arg_key_tokens=arg_key_tokens, path_tokens=path_tokens) for fn in funcs]
    scored.sort(key=lambda item: (-int(item["score"]), str(item["name_hash"])))
    top = scored[0] if scored else None
    second_score = int(scored[1]["score"]) if len(scored) > 1 else 0
    top_score = int(top["score"]) if top else 0
    top_count = sum(1 for item in scored if int(item["score"]) == top_score) if scored else 0
    margin = top_score - second_score
    high_margin = bool(top and top_score >= MIN_TOP_SCORE and margin >= HIGH_MARGIN_THRESHOLD and top_count == 1)
    return {
        "schema_option_count": len(funcs),
        "raw_response_present": bool(capture and (capture.get("raw_response") is not None or capture.get("raw_response_text"))),
        "prompt_present": bool(prompt.strip()),
        "dataset_schema_present": bool(funcs),
        "top_score": top_score,
        "second_score": second_score,
        "margin": margin,
        "top_count": top_count,
        "high_margin": high_margin,
        "top3_non_ambiguous": bool(top and top_score > 0 and top_count == 1),
        "all_tied_or_low_margin": bool(not top or top_score < MIN_TOP_SCORE or margin < HIGH_MARGIN_THRESHOLD),
        "multiple_high_margin": bool(top and top_score >= MIN_TOP_SCORE and top_count > 1),
        "no_signal": bool(not top or top_score == 0),
        "raw_support": bool(top and top.get("raw_support")),
        "prompt_support": bool(top and top.get("prompt_support")),
        "parameter_support": bool(top and top.get("parameter_support")),
        "class_or_path_support": bool(top and top.get("class_or_path_support")),
    }


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
        "audited_bucket_case_count": 0,
        "raw_response_present_count": 0,
        "prompt_or_current_turn_present_count": 0,
        "dataset_schema_present_count": 0,
        "schema_option_count_total": 0,
        "forbidden_field_violation_count": 0,
        "single_schema_high_margin_count": 0,
        "top1_schema_margin_ge_threshold_count": 0,
        "top3_schema_non_ambiguous_count": 0,
        "all_schema_scores_tied_or_low_margin_count": 0,
        "multiple_high_margin_schema_candidates_count": 0,
        "no_retrievable_schema_signal_count": 0,
        "raw_emitted_tool_name_supports_top_schema_count": 0,
        "prompt_terms_support_top_schema_count": 0,
        "parameter_terms_support_top_schema_count": 0,
        "class_or_path_terms_support_top_schema_count": 0,
        "uses_gold_tool_identity_count": 0,
        "uses_gold_argument_value_count": 0,
        "uses_scorer_diff_count": 0,
        "would_change_arguments_count": 0,
        "would_change_call_count": 0,
        "would_change_call_order_count": 0,
        "ambiguous_rerank_reject_count": 0,
    }
    high_margin_hashes: list[str] = []
    ambiguous_hashes: list[str] = []
    for cid in target_cases:
        counters["audited_bucket_case_count"] += 1
        result = _case_rerank(dataset.get(cid), captures.get(cid))
        counters["schema_option_count_total"] += int(result["schema_option_count"])
        if result["raw_response_present"]:
            counters["raw_response_present_count"] += 1
        if result["prompt_present"]:
            counters["prompt_or_current_turn_present_count"] += 1
        if result["dataset_schema_present"]:
            counters["dataset_schema_present_count"] += 1
        if result["high_margin"]:
            counters["single_schema_high_margin_count"] += 1
            high_margin_hashes.append(_hash_text(cid))
        if result["margin"] >= HIGH_MARGIN_THRESHOLD and result["top_count"] == 1:
            counters["top1_schema_margin_ge_threshold_count"] += 1
        if result["top3_non_ambiguous"]:
            counters["top3_schema_non_ambiguous_count"] += 1
        if result["all_tied_or_low_margin"]:
            counters["all_schema_scores_tied_or_low_margin_count"] += 1
        if result["multiple_high_margin"]:
            counters["multiple_high_margin_schema_candidates_count"] += 1
            counters["ambiguous_rerank_reject_count"] += 1
            ambiguous_hashes.append(_hash_text(cid))
        if result["no_signal"]:
            counters["no_retrievable_schema_signal_count"] += 1
        if result["raw_support"]:
            counters["raw_emitted_tool_name_supports_top_schema_count"] += 1
        if result["prompt_support"]:
            counters["prompt_terms_support_top_schema_count"] += 1
        if result["parameter_support"]:
            counters["parameter_terms_support_top_schema_count"] += 1
        if result["class_or_path_support"]:
            counters["class_or_path_terms_support_top_schema_count"] += 1
    input_case_count = len(target_cases)
    stop_reasons: list[str] = []
    if counters["single_schema_high_margin_count"] < 3:
        stop_reasons.append("single_schema_high_margin_below_3_of_10")
    if counters["multiple_high_margin_schema_candidates_count"] + counters["all_schema_scores_tied_or_low_margin_count"] >= 6:
        stop_reasons.append("ambiguous_or_low_margin_at_least_6_of_10")
    leakage_total = counters["uses_gold_tool_identity_count"] + counters["uses_gold_argument_value_count"] + counters["uses_scorer_diff_count"]
    if leakage_total:
        stop_reasons.append("leakage_counter_nonzero")
    if input_case_count - counters["prompt_or_current_turn_present_count"] > 2:
        stop_reasons.append("prompt_or_current_turn_unavailable_more_than_2_of_10")
    passed = not stop_reasons
    report = {
        "report_scope": "schema_retrieval_rerank_feasibility_diagnostic",
        "generated_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "server_path": "/cephfs/qiuyn/training-free",
        "branch": "stage1-bfcl-performance-sprint",
        "raw_root": str(raw_root),
        "dataset_json": str(dataset_json),
        "audit_only": True,
        "offline_only": True,
        "input_bucket": INPUT_BUCKET,
        "input_case_count": input_case_count,
        "candidate_extraction_authorized": False,
        "candidate_pool_authorized": False,
        "paired_scoring_authorized": False,
        "scorer_authorization": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "gold_text_emitted": False,
        "expected_values_emitted": False,
        "per_case_repair_recommendations_emitted": False,
        "no_leakage_to_candidate_pool": True,
        "rerank_method": "deterministic_lexical_schema_overlap_only",
        "does_not_use_embeddings_llm_provider_or_gold_target": True,
        "counters": counters,
        "case_hash_samples": {
            "single_schema_high_margin": high_margin_hashes[:5],
            "ambiguous_rerank_reject": ambiguous_hashes[:5],
        },
        "stop_gates": {
            "passed": passed,
            "stop_reasons": stop_reasons,
            "single_schema_high_margin_threshold": "at_least_3_of_10",
            "ambiguous_or_low_margin_stop_threshold": "at_least_6_of_10",
        },
        "decision": {
            "recommendation": "separate_approval_packet_only_do_not_generate_candidates" if passed else "stop_no_yield_research_review",
            "candidate_generation_authorized": False,
            "performance_evidence": False,
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
        "audited_bucket_case_count", "raw_response_present_count", "prompt_or_current_turn_present_count",
        "dataset_schema_present_count", "schema_option_count_total", "forbidden_field_violation_count",
        "single_schema_high_margin_count", "top1_schema_margin_ge_threshold_count",
        "top3_schema_non_ambiguous_count", "all_schema_scores_tied_or_low_margin_count",
        "multiple_high_margin_schema_candidates_count", "no_retrievable_schema_signal_count",
        "raw_emitted_tool_name_supports_top_schema_count", "prompt_terms_support_top_schema_count",
        "parameter_terms_support_top_schema_count", "class_or_path_terms_support_top_schema_count",
        "uses_gold_tool_identity_count", "uses_gold_argument_value_count", "uses_scorer_diff_count",
        "would_change_arguments_count", "would_change_call_count", "would_change_call_order_count",
        "ambiguous_rerank_reject_count",
    ]
    lines = [
        "# Schema Retrieval Rerank Feasibility Diagnostic", "",
        "Offline deterministic lexical/schema-overlap audit over the raw-payload schema-not-matched bucket only. No embeddings, LLM/provider rerank, scorer target, candidates, or performance claim.", "",
        "## Flags", "",
    ]
    for key in ["audit_only", "offline_only", "input_bucket", "input_case_count", "candidate_extraction_authorized", "candidate_pool_authorized", "paired_scoring_authorized", "scorer_authorization", "performance_evidence", "sota_3pp_claim_ready", "huawei_acceptance_ready", "gold_text_emitted", "expected_values_emitted", "per_case_repair_recommendations_emitted", "no_leakage_to_candidate_pool"]:
        value = report[key]
        lines.append(f"- {key}: `{str(value).lower() if isinstance(value, bool) else value}`")
    lines += ["", "## Counters", "", "| counter | value |", "| --- | ---: |"]
    for key in keys:
        lines.append(f"| {key} | {c.get(key, 0)} |")
    lines += ["", "## Stop Gates", "", f"- passed: `{str(report['stop_gates']['passed']).lower()}`", f"- stop_reasons: `{json.dumps(report['stop_gates']['stop_reasons'], sort_keys=True)}`", f"- recommendation: `{report['decision']['recommendation']}`"]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline schema retrieval/rerank feasibility diagnostic.")
    parser.add_argument("--raw-root", type=Path, default=DEFAULT_RAW_ROOT)
    parser.add_argument("--dataset-json", type=Path, default=DEFAULT_DATASET_JSON)
    parser.add_argument("--categories", default="multi_turn_miss_func,multi_turn_base,multi_turn_long_context")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = build_report(raw_root=args.raw_root, dataset_json=args.dataset_json, categories=args.categories, output_json=args.output, markdown_output=args.markdown_output)
    if args.compact:
        print(json.dumps({"counters": report["counters"], "stop_gates": report["stop_gates"], "decision": report["decision"]}, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
