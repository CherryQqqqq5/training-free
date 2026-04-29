#!/usr/bin/env python3
"""Fail-closed explicit-literal candidate-pool gate.

This checker is offline-only. It validates the candidate JSONL and the dev /
holdout manifests that authorize an explicit-required-argument-literal scorer
route after provider green. It does not run BFCL, a model, or a scorer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1")
DEFAULT_CANDIDATES = DEFAULT_ROOT / "candidate_rules.jsonl"
DEFAULT_DEV = DEFAULT_ROOT / "explicit_required_arg_literal_dev20_manifest.json"
DEFAULT_HOLDOUT = DEFAULT_ROOT / "explicit_required_arg_literal_holdout20_manifest.json"
DEFAULT_OUT = DEFAULT_ROOT / "explicit_literal_candidate_pool_gate.json"
DEFAULT_MD = DEFAULT_ROOT / "explicit_literal_candidate_pool_gate.md"

REQUIRED_CANDIDATE_FIELDS = (
    "case_id",
    "category",
    "candidate_generatable",
    "candidate_origin",
    "candidate_rules_type",
    "rule_type",
    "source_run_root",
    "tool",
    "schema_arg_name",
    "selected_literal",
    "literal_source",
    "literal_source_span",
    "literal_source_text_hash",
    "used_gold_fields",
    "used_score_fields",
    "used_candidate_output",
    "retention_prior",
)
FORBIDDEN_SOURCE_TOKENS = {
    "gold",
    "answer",
    "expected",
    "ground_truth",
    "oracle",
    "checker",
    "reference",
    "possible_answer",
}
ALLOWED_PROVENANCE_FLAG_KEYS = {
    "used_gold_fields",
    "used_score_fields",
    "used_candidate_output",
}
ALLOWED_LITERAL_SOURCES = {"current_request", "current_observation"}


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], str | None]:
    if not path.exists():
        return [], "candidate_jsonl_missing"
    records: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                return [], "candidate_jsonl_invalid"
            records.append(value)
    except Exception:
        return [], "candidate_jsonl_invalid"
    return records, None


def _case_ids(manifest: dict[str, Any]) -> list[str]:
    return [str(item) for item in manifest.get("selected_case_ids") or []]


def _duplicates(values: list[str]) -> list[str]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(value for value, count in counts.items() if count > 1)


def _contains_forbidden_token(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).lower()
            if lowered not in ALLOWED_PROVENANCE_FLAG_KEYS and any(token in lowered for token in FORBIDDEN_SOURCE_TOKENS):
                return True
            if _contains_forbidden_token(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_token(item) for item in value)
    elif isinstance(value, str):
        lowered = value.lower()
        return any(token in lowered for token in FORBIDDEN_SOURCE_TOKENS)
    return False


def _record_missing_fields(record: dict[str, Any]) -> list[str]:
    missing = [field for field in REQUIRED_CANDIDATE_FIELDS if record.get(field) in (None, "", [])]
    retention = record.get("retention_prior")
    if not isinstance(retention, dict):
        missing.append("retention_prior")
    elif retention.get("retain_eligibility") in (None, ""):
        missing.append("retention_prior.retain_eligibility")
    if record.get("used_gold_fields") is not False:
        missing.append("used_gold_fields=false")
    if record.get("used_score_fields") is not False:
        missing.append("used_score_fields=false")
    if record.get("used_candidate_output") is not False:
        missing.append("used_candidate_output=false")
    return sorted(set(missing))


def _eligible(record: dict[str, Any]) -> bool:
    retention = record.get("retention_prior") if isinstance(record.get("retention_prior"), dict) else {}
    return bool(
        record.get("candidate_generatable") is True
        and record.get("candidate_rules_type") == "explicit_required_arg_literal_completion"
        and record.get("rule_type") == "explicit_required_arg_literal_completion"
        and retention.get("retain_eligibility") == "demote_candidate"
        and str(record.get("literal_source")) in ALLOWED_LITERAL_SOURCES
        and not _record_missing_fields(record)
        and not _contains_forbidden_token(record)
    )


def evaluate(
    candidate_jsonl: Path = DEFAULT_CANDIDATES,
    dev_manifest: Path = DEFAULT_DEV,
    holdout_manifest: Path = DEFAULT_HOLDOUT,
    *,
    min_eligible: int = 35,
    dev_count: int = 20,
    holdout_count: int = 20,
) -> dict[str, Any]:
    records, load_error = _load_jsonl(candidate_jsonl)
    dev = _load_json(dev_manifest, {}) or {}
    holdout = _load_json(holdout_manifest, {}) or {}
    dev_ids = _case_ids(dev)
    holdout_ids = _case_ids(holdout)
    candidate_ids = [str(record.get("case_id")) for record in records if record.get("case_id") not in (None, "")]

    missing_by_case = []
    forbidden_cases = []
    bad_literal_source_cases = []
    source_result_only_cases = []
    missing_span_cases = []
    for idx, record in enumerate(records):
        case_id = str(record.get("case_id") or f"index:{idx}")
        missing = _record_missing_fields(record)
        if missing:
            missing_by_case.append({"case_id": case_id, "missing": missing})
        if _contains_forbidden_token(record):
            forbidden_cases.append(case_id)
        literal_source = str(record.get("literal_source") or "")
        if literal_source == "source_result_only" or record.get("grounding_rejection_reason") == "source_result_only":
            source_result_only_cases.append(case_id)
        if literal_source not in ALLOWED_LITERAL_SOURCES:
            bad_literal_source_cases.append(case_id)
        if record.get("literal_source_span") in (None, "", {}) or record.get("literal_source_text_hash") in (None, ""):
            missing_span_cases.append(case_id)

    eligible_ids = [str(record["case_id"]) for record in records if _eligible(record)]
    duplicate_candidate_ids = _duplicates(candidate_ids)
    dev_duplicates = _duplicates(dev_ids)
    holdout_duplicates = _duplicates(holdout_ids)
    overlap = sorted(set(dev_ids) & set(holdout_ids))

    blockers: list[str] = []
    if load_error:
        blockers.append(load_error)
    if not dev_manifest.exists():
        blockers.append("dev_manifest_missing")
    if not holdout_manifest.exists():
        blockers.append("holdout_manifest_missing")
    if len(eligible_ids) < min_eligible:
        blockers.append("eligible_explicit_literal_candidates_below_35")
    if missing_by_case:
        blockers.append("candidate_required_fields_missing")
    if forbidden_cases:
        blockers.append("candidate_gold_leakage_detected")
    if bad_literal_source_cases:
        blockers.append("candidate_literal_source_not_current_context")
    if source_result_only_cases:
        blockers.append("source_result_only_candidates_are_diagnostic_only")
    if missing_span_cases:
        blockers.append("literal_span_or_hash_missing")
    if duplicate_candidate_ids:
        blockers.append("candidate_duplicate_case_ids_present")
    if dev_duplicates:
        blockers.append("dev_duplicate_case_ids_present")
    if holdout_duplicates:
        blockers.append("holdout_duplicate_case_ids_present")
    if overlap:
        blockers.append("dev_holdout_overlap_present")
    if len(dev_ids) != dev_count:
        blockers.append("dev20_count_not_met")
    if len(holdout_ids) != holdout_count:
        blockers.append("holdout20_count_not_met")
    if dev.get("planned_commands") or dev.get("candidate_commands") or holdout.get("planned_commands") or holdout.get("candidate_commands"):
        blockers.append("scorer_commands_present_in_manifests")

    return {
        "report_scope": "explicit_literal_candidate_pool_gate",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_jsonl": str(candidate_jsonl),
        "dev_manifest": str(dev_manifest),
        "holdout_manifest": str(holdout_manifest),
        "candidate_record_count": len(records),
        "eligible_count": len(eligible_ids),
        "min_eligible": min_eligible,
        "eligible_case_ids": eligible_ids,
        "dev_selected_case_count": len(dev_ids),
        "holdout_selected_case_count": len(holdout_ids),
        "required_dev_count": dev_count,
        "required_holdout_count": holdout_count,
        "duplicate_candidate_case_ids": duplicate_candidate_ids,
        "dev_duplicate_case_ids": dev_duplicates,
        "holdout_duplicate_case_ids": holdout_duplicates,
        "dev_holdout_overlap_case_ids": overlap,
        "missing_fields_by_case": missing_by_case,
        "forbidden_gold_leakage_case_ids": sorted(set(forbidden_cases)),
        "bad_literal_source_case_ids": sorted(set(bad_literal_source_cases)),
        "source_result_only_diagnostic_case_ids": sorted(set(source_result_only_cases)),
        "missing_literal_span_or_hash_case_ids": sorted(set(missing_span_cases)),
        "explicit_literal_candidate_pool_passed": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Explicit Literal Candidate Pool Gate",
        "",
        f"- Passed: `{report['explicit_literal_candidate_pool_passed']}`",
        f"- Eligible count: `{report['eligible_count']}` / `{report['min_eligible']}`",
        f"- Dev count: `{report['dev_selected_case_count']}` / `{report['required_dev_count']}`",
        f"- Holdout count: `{report['holdout_selected_case_count']}` / `{report['required_holdout_count']}`",
        f"- Blockers: `{report['blockers']}`",
        "",
        "Offline-only. This checker does not run BFCL, a model, or a scorer.",
        "",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-jsonl", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--dev-manifest", type=Path, default=DEFAULT_DEV)
    parser.add_argument("--holdout-manifest", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--min-eligible", type=int, default=35)
    parser.add_argument("--dev-count", type=int, default=20)
    parser.add_argument("--holdout-count", type=int, default=20)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    report = evaluate(
        args.candidate_jsonl,
        args.dev_manifest,
        args.holdout_manifest,
        min_eligible=args.min_eligible,
        dev_count=args.dev_count,
        holdout_count=args.holdout_count,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "explicit_literal_candidate_pool_passed",
            "eligible_count",
            "dev_selected_case_count",
            "holdout_selected_case_count",
            "blockers",
        ]}, indent=2, sort_keys=True))
    if args.strict and not report["explicit_literal_candidate_pool_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
