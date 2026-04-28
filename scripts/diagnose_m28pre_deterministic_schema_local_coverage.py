#!/usr/bin/env python3
"""Audit M2.8-pre deterministic schema-local non-live repair coverage.

Offline diagnostic only. Reads BFCL dataset schemas and baseline/source results;
does not run BFCL, models, or scorers.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from grc.compiler.retention_priors import DEMOTE_CANDIDATE
from scripts.build_m28pre_explicit_required_arg_literal import (
    DEFAULT_OUT_ROOT,
    DEFAULT_SOURCE_MANIFEST,
    _compile_deterministic_schema_local_records,
    _load_dataset_records,
    _load_result_records,
)

OUT = DEFAULT_OUT_ROOT / "deterministic_schema_local_coverage_audit.json"
MD = DEFAULT_OUT_ROOT / "deterministic_schema_local_coverage_audit.md"


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


def _group_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str], Counter[str]] = defaultdict(Counter)
    for row in records:
        key = (
            str(row.get("category") or "unknown"),
            str(row.get("tool") or "unknown"),
            str(row.get("arg_key") or row.get("schema_arg_name") or "unknown"),
            str(row.get("repair_kind") or "unknown"),
        )
        reason = str(row.get("rejection_reason") or "retain_prior_candidate")
        grouped[key][reason] += 1
    return [
        {
            "category": category,
            "tool": tool,
            "arg_key": arg_key,
            "repair_kind": repair_kind,
            "counts": dict(sorted(counts.items())),
            "total": sum(counts.values()),
        }
        for (category, tool, arg_key, repair_kind), counts in sorted(grouped.items())
    ]


def _route(candidate_count: int, reasons: Counter[str]) -> tuple[str, list[str]]:
    blockers: list[str] = []
    if candidate_count < 20:
        blockers.append("deterministic_schema_local_demote_below_20")
    if candidate_count == 0:
        blockers.append("deterministic_schema_local_family_coverage_zero")
    parser_like = reasons.get("missing_source_result", 0) + reasons.get("missing_schema_properties", 0) + reasons.get("arg_key_not_in_schema_properties", 0)
    true_low = reasons.get("no_deterministic_schema_local_repair_detected", 0) + reasons.get("already_schema_local_canonical", 0)
    if candidate_count >= 20:
        return "combine_with_explicit_prior_pool", blockers
    if parser_like > true_low:
        return "fix_parser_or_source_result_layout", blockers
    if candidate_count == 0:
        return "define_next_theory_family_after_deterministic_schema_local_non_live_repair", blockers
    return "deterministic_schema_local_non_live_repair_coverage_insufficient", blockers


def evaluate(source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST) -> dict[str, Any]:
    manifest = _read_json(source_manifest_path, {}) or {}
    records: list[dict[str, Any]] = []
    scanned_categories: set[str] = set()
    for row in manifest.get("category_status") or []:
        if not row.get("source_artifacts_available"):
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
            for case_id, result in results.items():
                entry = entries.get(case_id)
                if entry is None:
                    records.append({
                        "case_id": case_id,
                        "category": category,
                        "source_run_root": str(root),
                        "candidate_generatable": False,
                        "rejection_reason": "source_result_case_not_in_dataset",
                    })
                    continue
                rows = _compile_deterministic_schema_local_records(entry, result, root, category)
                records.extend(rows)
    candidate_rows = [row for row in records if row.get("candidate_generatable") and (row.get("retention_prior") or {}).get("retain_eligibility") == DEMOTE_CANDIDATE]
    reasons = Counter(str(row.get("rejection_reason") or "retain_prior_candidate") for row in records)
    route, blockers = _route(len(candidate_rows), reasons)
    report = {
        "report_scope": "m28pre_deterministic_schema_local_coverage_audit",
        "offline_only": True,
        "candidate_commands": [],
        "planned_commands": [],
        "deterministic_schema_local_coverage_audit_ready": True,
        "deterministic_schema_local_candidate_count": len(candidate_rows),
        "deterministic_schema_local_demote_candidate_count": len(candidate_rows),
        "deterministic_schema_local_family_coverage_zero": len(candidate_rows) == 0,
        "deterministic_schema_local_ambiguous_count": reasons.get("ambiguous_enum_canonicalization", 0) + reasons.get("ambiguous_or_non_deterministic_schema_repair", 0),
        "deterministic_schema_local_value_creation_count": sum(1 for row in records if row.get("value_creation") is True or row.get("gold_value_mutation") is True),
        "rejection_reason_counts": dict(sorted(reasons.items())),
        "category_tool_arg_repair_counts": _group_records(records),
        "scanned_categories": sorted(scanned_categories),
        "route_recommendation": route,
        "blockers": blockers,
        "records": records,
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.8-pre Deterministic Schema-Local Coverage Audit",
        "",
        f"- Audit ready: `{report['deterministic_schema_local_coverage_audit_ready']}`",
        f"- Demote candidates: `{report['deterministic_schema_local_demote_candidate_count']}`",
        f"- Coverage zero: `{report['deterministic_schema_local_family_coverage_zero']}`",
        f"- Route recommendation: `{report['route_recommendation']}`",
        f"- Blockers: `{report['blockers']}`",
        "",
        "| Rejection reason | Count |",
        "| --- | ---: |",
    ]
    for reason, count in (report.get("rejection_reason_counts") or {}).items():
        lines.append(f"| `{reason}` | `{count}` |")
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
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "deterministic_schema_local_coverage_audit_ready",
            "deterministic_schema_local_demote_candidate_count",
            "deterministic_schema_local_family_coverage_zero",
            "route_recommendation",
            "blockers",
            "candidate_commands",
            "planned_commands",
        ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
