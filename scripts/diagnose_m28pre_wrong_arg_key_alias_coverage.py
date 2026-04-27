#!/usr/bin/env python3
"""Audit M2.8-pre wrong-arg-key alias coverage.

This is a compact offline diagnostic. It reads BFCL dataset schemas and
baseline/source results, but does not run BFCL, models, or scorers.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from grc.compiler.retention_priors import DEMOTE_CANDIDATE, wrong_arg_key_alias_prior

from scripts.build_m28pre_explicit_required_arg_literal import (
    DEFAULT_OUT_ROOT,
    DEFAULT_SOURCE_MANIFEST,
    PRIOR_AWARE_EXCLUDED_CATEGORIES,
    _canonical_alias_candidates,
    _function_map,
    _iter_tool_calls,
    _load_dataset_records,
    _load_result_records,
    _normalize_tool_name,
    _scalar,
)

OUT = DEFAULT_OUT_ROOT / "wrong_arg_key_alias_coverage_audit.json"
MD = DEFAULT_OUT_ROOT / "wrong_arg_key_alias_coverage_audit.md"


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def _base_record(category: str, source_root: Path, case_id: str, *, reason: str, tool: str | None = None) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "category": category,
        "source_run_root": str(source_root),
        "tool": tool,
        "original_arg_key": None,
        "schema_canonical_keys": [],
        "alias_candidates": [],
        "selected_canonical_key": None,
        "alias_evidence": None,
        "arg_value": None,
        "value_mutation": False,
        "tool_call_mapping_unique": None,
        "retain_prior_candidate": False,
        "rejection_reason": reason,
    }


def _audit_case(category: str, source_root: Path, entry: dict[str, Any], result: dict[str, Any] | None) -> list[dict[str, Any]]:
    case_id = str(entry.get("id") or "")
    if category in PRIOR_AWARE_EXCLUDED_CATEGORIES:
        return [_base_record(category, source_root, case_id, reason="memory_or_hidden_state_category_excluded")]
    if not result:
        return [_base_record(category, source_root, case_id, reason="missing_source_result")]
    calls = _iter_tool_calls(result.get("result"))
    if not calls:
        return [_base_record(category, source_root, case_id, reason="missing_emitted_tool_call")]

    calls_by_tool: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for tool, args in calls:
        calls_by_tool[_normalize_tool_name(tool)].append((tool, args))

    rows: list[dict[str, Any]] = []
    matched_any_schema_tool = False
    for norm_tool, fn in _function_map(entry).items():
        if norm_tool not in calls_by_tool:
            continue
        matched_any_schema_tool = True
        props = (fn.get("parameters") or {}).get("properties") or {}
        canonical_keys = [str(key) for key in props.keys()] if isinstance(props, dict) else []
        if len(calls_by_tool[norm_tool]) != 1:
            rows.append({
                **_base_record(category, source_root, case_id, reason="parallel_call_mapping_not_unique", tool=norm_tool),
                "schema_canonical_keys": canonical_keys,
                "tool_call_mapping_unique": False,
            })
            continue
        emitted_tool, emitted_args = calls_by_tool[norm_tool][0]
        if not canonical_keys:
            rows.append({
                **_base_record(category, source_root, case_id, reason="missing_schema_properties", tool=norm_tool),
                "emitted_tool_name": emitted_tool,
                "tool_call_mapping_unique": True,
            })
            continue
        if not emitted_args:
            rows.append({
                **_base_record(category, source_root, case_id, reason="missing_emitted_tool_args", tool=norm_tool),
                "emitted_tool_name": emitted_tool,
                "schema_canonical_keys": canonical_keys,
                "tool_call_mapping_unique": True,
            })
            continue

        emitted_any_arg = False
        for original_key, value in emitted_args.items():
            original_key = str(original_key)
            scalar_value = _scalar(value)
            common = {
                "case_id": case_id,
                "category": category,
                "source_run_root": str(source_root),
                "tool": norm_tool,
                "emitted_tool_name": emitted_tool,
                "original_arg_key": original_key,
                "schema_canonical_keys": canonical_keys,
                "arg_value": scalar_value,
                "value_mutation": False,
                "tool_call_mapping_unique": True,
                "retain_prior_candidate": False,
            }
            emitted_any_arg = True
            if original_key in canonical_keys:
                rows.append({
                    **common,
                    "alias_candidates": [],
                    "selected_canonical_key": original_key,
                    "alias_evidence": "already_canonical_schema_key",
                    "rejection_reason": "no_wrong_arg_key_alias_detected",
                })
                continue
            if scalar_value is None or str(scalar_value).strip() == "" or len(str(scalar_value)) > 240:
                rows.append({
                    **common,
                    "alias_candidates": [],
                    "selected_canonical_key": None,
                    "alias_evidence": None,
                    "rejection_reason": "missing_or_non_scalar_arg_value",
                })
                continue
            candidates = _canonical_alias_candidates(original_key, canonical_keys)
            if len(candidates) != 1:
                rows.append({
                    **common,
                    "alias_candidates": [candidate for candidate, _evidence in candidates],
                    "selected_canonical_key": None,
                    "alias_evidence": None,
                    "rejection_reason": "ambiguous_alias" if candidates else "no_schema_alias_match",
                })
                continue
            canonical_key, evidence = candidates[0]
            if canonical_key in emitted_args:
                rows.append({
                    **common,
                    "alias_candidates": [canonical_key],
                    "selected_canonical_key": canonical_key,
                    "alias_evidence": evidence,
                    "rejection_reason": "canonical_key_already_present",
                })
                continue
            prior_row = {
                "rule_type": "wrong_arg_key_alias_repair",
                "candidate_rules_type": "wrong_arg_key_alias_repair",
                "original_arg_key": original_key,
                "canonical_arg_key": canonical_key,
                "schema_arg_name": canonical_key,
                "arg_value": scalar_value,
                "value_source": "model_emitted_args",
                "alias_ambiguous": False,
                "no_next_tool_intervention": True,
                "exact_tool_choice": False,
                "ctspc_v0_action_rule": False,
                "tool_choice_mutation": False,
                "trajectory_mutation": False,
                "value_mutation": False,
            }
            prior = wrong_arg_key_alias_prior(prior_row)
            rows.append({
                **common,
                "alias_candidates": [canonical_key],
                "selected_canonical_key": canonical_key,
                "alias_evidence": evidence,
                "retain_prior_candidate": prior.get("retain_eligibility") == DEMOTE_CANDIDATE,
                "retention_prior": prior,
                "rejection_reason": None if prior.get("retain_eligibility") == DEMOTE_CANDIDATE else prior.get("prior_rejection_reason"),
            })
        if not emitted_any_arg:
            rows.append({
                **_base_record(category, source_root, case_id, reason="missing_emitted_tool_args", tool=norm_tool),
                "emitted_tool_name": emitted_tool,
                "schema_canonical_keys": canonical_keys,
                "tool_call_mapping_unique": True,
            })

    if rows:
        return rows
    if not matched_any_schema_tool:
        return [_base_record(category, source_root, case_id, reason="no_matching_emitted_tool")]
    return [_base_record(category, source_root, case_id, reason="no_wrong_arg_key_alias_detected")]


def _group_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for row in records:
        key = (str(row.get("category") or "unknown"), str(row.get("tool") or "unknown"), str(row.get("original_arg_key") or "unknown"))
        reason = str(row.get("rejection_reason") or "retain_prior_candidate")
        grouped[key][reason] += 1
    return [
        {
            "category": category,
            "tool": tool,
            "original_arg_key": original_key,
            "reason_counts": dict(sorted(counter.items())),
            "record_count": sum(counter.values()),
        }
        for (category, tool, original_key), counter in sorted(grouped.items())
    ]


def _route(reasons: Counter[str], candidate_count: int) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if candidate_count:
        return "fix_compiler_alias_candidate_integration", blockers
    blockers.append("wrong_arg_key_alias_family_coverage_zero")
    no_schema = reasons.get("no_schema_alias_match", 0)
    parser = sum(reasons.get(reason, 0) for reason in [
        "missing_source_result",
        "missing_emitted_tool_call",
        "missing_emitted_tool_args",
        "no_matching_emitted_tool",
        "parallel_call_mapping_not_unique",
        "missing_schema_properties",
    ])
    canonical_like = reasons.get("no_wrong_arg_key_alias_detected", 0) + reasons.get("canonical_key_already_present", 0)
    if no_schema > max(parser, canonical_like, 0):
        blockers.append("deterministic_alias_table_may_be_too_narrow")
        return "expand_deterministic_alias_table_then_rescan", blockers
    if parser > max(no_schema, canonical_like, 0):
        blockers.append("alias_parser_or_call_mapping_issue_dominates")
        return "fix_alias_audit_parser_or_call_mapping", blockers
    if canonical_like > 0:
        blockers.append("baseline_emitted_args_mostly_canonical_or_no_alias")
    return "pivot_to_next_theory_family=deterministic_schema_local_non_live_repair", blockers


def evaluate(source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST) -> dict[str, Any]:
    manifest = _read_json(source_manifest_path, {}) or {}
    records: list[dict[str, Any]] = []
    scanned_categories: set[str] = set()
    for row in manifest.get("category_status") or []:
        if not isinstance(row, dict) or not row.get("source_artifacts_available"):
            continue
        category = str(row.get("category") or "")
        roots = [Path(str(root)) for root in row.get("existing_source_roots") or []]
        if not category or not roots:
            continue
        entries = _load_dataset_records(category)
        if not entries:
            continue
        scanned_categories.add(category)
        for root in roots:
            results = _load_result_records(root, category)
            for case_id, entry in entries.items():
                records.extend(_audit_case(category, root, entry, results.get(case_id)))

    reasons = Counter(str(row.get("rejection_reason") or "retain_prior_candidate") for row in records)
    candidate_count = sum(1 for row in records if row.get("retain_prior_candidate"))
    route, blockers = _route(reasons, candidate_count)
    return {
        "report_scope": "m28pre_wrong_arg_key_alias_coverage_audit",
        "offline_only": True,
        "candidate_commands": [],
        "planned_commands": [],
        "wrong_arg_key_alias_coverage_audit_ready": True,
        "wrong_arg_key_alias_candidate_count": candidate_count,
        "wrong_arg_key_alias_demote_candidate_count": candidate_count,
        "wrong_arg_key_alias_family_coverage_zero": candidate_count == 0,
        "rejection_reason_counts": dict(sorted(reasons.items())),
        "category_tool_key_counts": _group_records(records),
        "scanned_categories": sorted(scanned_categories),
        "route_recommendation": route,
        "blockers": blockers,
        "records": records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.8-pre Wrong Arg Key Alias Coverage Audit",
        "",
        f"- Audit ready: `{report['wrong_arg_key_alias_coverage_audit_ready']}`",
        f"- Demote candidates: `{report['wrong_arg_key_alias_demote_candidate_count']}`",
        f"- Coverage zero: `{report['wrong_arg_key_alias_family_coverage_zero']}`",
        f"- Route recommendation: `{report['route_recommendation']}`",
        f"- Blockers: `{report['blockers']}`",
        "",
        "## Rejection Reasons",
    ]
    for reason, count in report.get("rejection_reason_counts", {}).items():
        lines.append(f"- `{reason}`: `{count}`")
    lines.extend(["", "## Category / Tool / Key Aggregates", "", "| Category | Tool | Original key | Records | Reasons |", "| --- | --- | --- | ---: | --- |"])
    for row in report.get("category_tool_key_counts", [])[:80]:
        lines.append(f"| `{row.get('category')}` | `{row.get('tool')}` | `{row.get('original_arg_key')}` | `{row.get('record_count')}` | `{row.get('reason_counts')}` |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.source_manifest)
    _write_json(args.output, report)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "wrong_arg_key_alias_coverage_audit_ready",
            "wrong_arg_key_alias_demote_candidate_count",
            "wrong_arg_key_alias_family_coverage_zero",
            "route_recommendation",
            "blockers",
            "rejection_reason_counts",
            "planned_commands",
            "candidate_commands",
        ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
