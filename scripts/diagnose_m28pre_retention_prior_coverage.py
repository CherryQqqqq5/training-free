#!/usr/bin/env python3
"""Audit theory-prior coverage for M2.8-pre explicit literal retention.

This diagnostic answers whether explicit_required_arg_literal_completion has
current-context anchored opportunities, without relaxing the retention prior or
emitting scorer commands.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from grc.compiler.retention_priors import (
    DEMOTE_CANDIDATE,
    EXPLICIT_REQUIRED_ARG_LITERAL_FAMILY,
    evaluate_retention_prior,
)

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1")
DEFAULT_SOURCE_MANIFEST = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_manifest.json")
OUT = DEFAULT_ROOT / "retention_prior_coverage_audit.json"
MD = DEFAULT_ROOT / "retention_prior_coverage_audit.md"

BUCKET_CURRENT_CONTEXT = "current_context_anchored_literal_candidate"
BUCKET_SOURCE_RESULT_ONLY = "source_result_only_diagnostic_candidate"
BUCKET_AMBIGUOUS = "ambiguous_current_context_literal_candidate"
BUCKET_NO_OBSERVABLE = "no_observable_literal_case"

CURRENT_CONTEXT_SOURCES = {
    "current_request",
    "current_observation",
    "current_request_or_current_observation",
}
AMBIGUOUS_REASONS = {
    "ambiguous_literal",
    "ambiguous_or_missing_observable_literal",
    "multiple_observable_literals",
    "schema_type_ambiguous",
}
NO_OBSERVABLE_REASONS = {
    "missing_source_result",
    "required_args_already_present_or_no_matching_emitted_tool",
    "missing_current_request_or_observation",
    "missing_emitted_tool_call",
    "memory_or_hidden_state_category_excluded",
    "parallel_call_mapping_not_unique",
    "multiple_missing_required_args",
    "no_matching_scalar_required_arg",
}


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_explicit_family(row: dict[str, Any]) -> bool:
    prior = row.get("retention_prior") if isinstance(row.get("retention_prior"), dict) else {}
    return any(
        str(value or "") == EXPLICIT_REQUIRED_ARG_LITERAL_FAMILY
        for value in [
            row.get("candidate_rules_type"),
            row.get("rule_type"),
            row.get("rule_family"),
            prior.get("rule_family"),
        ]
    )


def _source(row: dict[str, Any], prior: dict[str, Any]) -> str:
    return str(
        row.get("literal_source")
        or row.get("literal_source_observed_as")
        or row.get("literal_source_anchor")
        or prior.get("literal_source_observed_as")
        or prior.get("literal_source")
        or ""
    )


def _source_span(row: dict[str, Any], source: str) -> str | None:
    span = row.get("source_span") or row.get("literal_source_span") or row.get("literal_source_anchor")
    if span:
        return str(span)
    if source in CURRENT_CONTEXT_SOURCES:
        return source
    return None


def _literal_uniqueness(row: dict[str, Any], prior: dict[str, Any]) -> bool:
    if prior.get("literal_uniqueness") is True:
        return True
    try:
        return int(row.get("literal_candidate_count")) == 1
    except Exception:
        return False


def _schema_type_match(row: dict[str, Any], prior: dict[str, Any]) -> bool:
    return row.get("literal_type_match") is True or prior.get("schema_type_match") is True


def _rejection_reason(row: dict[str, Any], prior: dict[str, Any]) -> str | None:
    reason = row.get("rejection_reason") or row.get("prior_rejection_reason") or prior.get("prior_rejection_reason")
    return str(reason) if reason else None


def _bucket(row: dict[str, Any], prior: dict[str, Any], source: str, reason: str | None) -> str:
    eligibility = str(prior.get("retain_eligibility") or "")
    if (
        eligibility == DEMOTE_CANDIDATE
        and source in CURRENT_CONTEXT_SOURCES
        and _literal_uniqueness(row, prior)
        and _schema_type_match(row, prior)
    ):
        return BUCKET_CURRENT_CONTEXT
    if source == "source_result_tool_args" or reason == "literal_source_not_observable":
        return BUCKET_SOURCE_RESULT_ONLY
    if reason in AMBIGUOUS_REASONS:
        return BUCKET_AMBIGUOUS
    try:
        if int(row.get("literal_candidate_count")) > 1:
            return BUCKET_AMBIGUOUS
    except Exception:
        pass
    if reason in NO_OBSERVABLE_REASONS or not source or source == "unknown":
        return BUCKET_NO_OBSERVABLE
    return BUCKET_NO_OBSERVABLE


def _audit_record(row: dict[str, Any], source_file: str) -> dict[str, Any]:
    prior = evaluate_retention_prior(row)
    source = _source(row, prior)
    reason = _rejection_reason(row, prior)
    bucket = _bucket(row, prior, source, reason)
    return {
        "case_id": row.get("case_id"),
        "category": row.get("category"),
        "tool": row.get("tool") or row.get("emitted_tool_name"),
        "required_arg": row.get("required_arg") or row.get("schema_arg_name"),
        "literal_value": row.get("literal_value") or row.get("unique_literal_value"),
        "literal_source": source or None,
        "source_span": _source_span(row, source),
        "schema_type_match": _schema_type_match(row, prior),
        "literal_uniqueness": _literal_uniqueness(row, prior),
        "retain_eligibility": prior.get("retain_eligibility"),
        "rejection_reason": reason,
        "coverage_bucket": bucket,
        "source_file": source_file,
    }


def _explicit_rows(root: Path) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for name in ["candidate_rules.jsonl", "rejected_candidates.jsonl"]:
        for row in _read_jsonl(root / name):
            if _is_explicit_family(row):
                rows.append((name, row))
    return rows


def evaluate(root: Path = DEFAULT_ROOT, source_manifest_path: Path = DEFAULT_SOURCE_MANIFEST) -> dict[str, Any]:
    compiler = _read_json(root / "compiler_summary.json", {}) or {}
    source_manifest = _read_json(source_manifest_path, {}) or {}
    records = [_audit_record(row, source_file) for source_file, row in _explicit_rows(root)]
    counts = Counter(str(record["coverage_bucket"]) for record in records)
    bucket_counts = {
        BUCKET_CURRENT_CONTEXT: counts.get(BUCKET_CURRENT_CONTEXT, 0),
        BUCKET_SOURCE_RESULT_ONLY: counts.get(BUCKET_SOURCE_RESULT_ONLY, 0),
        BUCKET_AMBIGUOUS: counts.get(BUCKET_AMBIGUOUS, 0),
        BUCKET_NO_OBSERVABLE: counts.get(BUCKET_NO_OBSERVABLE, 0),
    }
    current_count = bucket_counts[BUCKET_CURRENT_CONTEXT]
    return {
        "report_scope": "m2_8pre_retention_prior_coverage_audit",
        "m28pre_retention_prior_coverage_audit_ready": True,
        "offline_only": True,
        "no_bfcl_or_model_call": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "candidate_rules_type": EXPLICIT_REQUIRED_ARG_LITERAL_FAMILY,
        "coverage_bucket_counts": bucket_counts,
        "current_context_anchored_literal_candidate_count": current_count,
        "source_result_only_diagnostic_candidate_count": bucket_counts[BUCKET_SOURCE_RESULT_ONLY],
        "ambiguous_current_context_literal_candidate_count": bucket_counts[BUCKET_AMBIGUOUS],
        "no_observable_literal_case_count": bucket_counts[BUCKET_NO_OBSERVABLE],
        "explicit_prior_family_coverage_zero": current_count == 0,
        "coverage_conclusion": "explicit_prior_family_coverage_zero" if current_count == 0 else "explicit_prior_family_has_current_context_coverage",
        "compiler_snapshot": {
            "selected_case_count": compiler.get("selected_case_count"),
            "candidate_generatable_count": compiler.get("candidate_generatable_count"),
            "retain_eligible_candidate_count": compiler.get("retain_eligible_candidate_count"),
            "theory_prior_explicit_literal_candidate_count": compiler.get("theory_prior_explicit_literal_candidate_count"),
            "retention_prior_distribution": compiler.get("retention_prior_distribution"),
            "prior_aware_scan": compiler.get("prior_aware_scan"),
        },
        "source_manifest_snapshot": {
            "source_collection_only": source_manifest.get("source_collection_only"),
            "no_candidate_rules": source_manifest.get("no_candidate_rules"),
            "candidate_commands": source_manifest.get("candidate_commands") or [],
            "planned_category_count": len(source_manifest.get("planned_commands") or []),
        },
        "records": records,
    }


def render_markdown(report: dict[str, Any]) -> str:
    counts = report["coverage_bucket_counts"]
    lines = [
        "# M2.8-pre Retention Prior Coverage Audit",
        "",
        "Offline diagnostic only. This audit does not emit scorer commands and does not relax retain priors.",
        "",
        f"- Audit ready: `{report['m28pre_retention_prior_coverage_audit_ready']}`",
        f"- Explicit prior family coverage zero: `{report['explicit_prior_family_coverage_zero']}`",
        f"- Coverage conclusion: `{report['coverage_conclusion']}`",
        "",
        "| Coverage bucket | Count |",
        "| --- | ---: |",
    ]
    for key in [BUCKET_CURRENT_CONTEXT, BUCKET_SOURCE_RESULT_ONLY, BUCKET_AMBIGUOUS, BUCKET_NO_OBSERVABLE]:
        lines.append(f"| `{key}` | `{counts.get(key, 0)}` |")
    lines.extend([
        "",
        "Bucket A requires current request/observation anchoring, unique literal evidence, schema type match, and `demote_candidate` retention prior.",
        "Source-result-only legacy diagnostics remain non-retainable.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(report: dict[str, Any], output: Path = OUT, markdown_output: Path = MD) -> None:
    _write_json(output, report)
    markdown_output.parent.mkdir(parents=True, exist_ok=True)
    markdown_output.write_text(render_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.root, args.source_manifest)
    write_outputs(report, args.output, args.markdown_output)
    if args.compact:
        print(json.dumps({
            "m28pre_retention_prior_coverage_audit_ready": report["m28pre_retention_prior_coverage_audit_ready"],
            "explicit_prior_family_coverage_zero": report["explicit_prior_family_coverage_zero"],
            "current_context_anchored_literal_candidate_count": report["current_context_anchored_literal_candidate_count"],
            "source_result_only_diagnostic_candidate_count": report["source_result_only_diagnostic_candidate_count"],
            "ambiguous_current_context_literal_candidate_count": report["ambiguous_current_context_literal_candidate_count"],
            "no_observable_literal_case_count": report["no_observable_literal_case_count"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
