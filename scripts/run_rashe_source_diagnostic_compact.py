#!/usr/bin/env python3
"""Plan-only runner for bounded RASHE compact source diagnostics.

This entrypoint makes the runbook command verifiable without executing source
collection. It validates the approved source lane, the after-source matrix, and
all signed run bounds. Dry-run/plan-only modes never call a provider, never read
API keys, and never write diagnostics.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from typing import Any

from scripts.check_rashe_source_real_trace_approved import APPROVED_CATEGORIES, FAILURE_BUCKETS

SIGNED_PROVIDER_PROFILES = ("Chuangzhi/Novacode", "Chuangzhi/Novacode gpt-5.2")
SIGNED_MODEL = "gpt-5.2"
SIGNED_OUTPUT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/")
SIGNED_SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json")
SIGNED_PUBLISH_FIELDS = (
    "category",
    "case_count",
    "provider_call_count",
    "raw_payload_tracked_count",
    "forbidden_field_violation_count",
    "failure_bucket_counts",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
)
FORBIDDEN_FIELD_NAMES = (
    "raw_case_id",
    "case_id",
    "raw_trace",
    "trace_path",
    "raw_provider_payload",
    "provider_payload",
    "raw_payload",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "candidate_output",
    "repair_output",
    "feedback",
    "holdout_feedback",
    "full_suite_feedback",
    "candidate_jsonl",
    "dev_manifest",
    "holdout_manifest",
    "full_manifest",
)
RAW_PATH_INDICATORS = (
    "raw_trace",
    "raw-trace",
    "raw_payload",
    "raw-payload",
    "case_id",
    "case-id",
    "provider_payload",
    "provider-payload",
    "candidate_jsonl",
    "candidate-jsonl",
    "scorer_diff",
    "scorer-diff",
    "scorer_output",
    "scorer-output",
    "gold",
    "expected",
    "reference",
    "repair_output",
    "repair-output",
    "holdout_feedback",
    "holdout-feedback",
    "full_suite_feedback",
    "full-suite-feedback",
)


def split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def run_json_checker(args: list[str]) -> tuple[bool, str | None, dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, result.stdout.strip() or result.stderr.strip() or "checker_failed", {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return False, f"checker_json_invalid:{args[0]}:{exc}", {}
    if not isinstance(data, dict):
        return False, f"checker_output_not_object:{args[0]}", {}
    return True, None, data


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def normalize_field(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def build_compact_plan(category: str, case_count: int) -> dict[str, Any]:
    return {
        "schema_version": "rashe_source_diagnostic_compact_v0",
        "category": category,
        "case_count": case_count,
        "provider_call_count": 0,
        "raw_payload_tracked_count": 0,
        "forbidden_field_violation_count": 0,
        "failure_bucket_counts": {bucket: 0 for bucket in FAILURE_BUCKETS},
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }


def validate_schema_artifact(schema: dict[str, Any], artifact: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    if set(artifact) != set(required):
        blockers.append("compact_artifact_fields_do_not_match_schema_required")
    allowed_categories = schema.get("properties", {}).get("category", {}).get("enum", [])
    if artifact.get("category") not in allowed_categories:
        blockers.append(f"compact_artifact_category_not_signed:{artifact.get('category')}")
    case_count = artifact.get("case_count")
    if not isinstance(case_count, int) or case_count < 0 or case_count > 50:
        blockers.append(f"compact_artifact_case_count_invalid:{case_count!r}")
    if artifact.get("provider_call_count") != 0:
        blockers.append(f"compact_artifact_provider_call_count_not_zero:{artifact.get('provider_call_count')!r}")
    for field in ["raw_payload_tracked_count", "forbidden_field_violation_count"]:
        if artifact.get(field) != 0:
            blockers.append(f"compact_artifact_{field}_not_zero:{artifact.get(field)!r}")
    for field in ["candidate_generation_authorized", "scorer_authorized", "performance_evidence"]:
        if artifact.get(field) is not False:
            blockers.append(f"compact_artifact_{field}_not_false:{artifact.get(field)!r}")
    buckets = artifact.get("failure_bucket_counts")
    if not isinstance(buckets, dict) or set(buckets) != set(FAILURE_BUCKETS):
        blockers.append("compact_artifact_failure_buckets_invalid")
    elif any((not isinstance(value, int) or value < 0) for value in buckets.values()):
        blockers.append("compact_artifact_failure_bucket_count_invalid")
    if schema.get("additionalProperties") is not False:
        blockers.append("compact_schema_additional_properties_not_false")
    return blockers


def validate_args(args: argparse.Namespace) -> tuple[list[str], list[str], list[str], int]:
    blockers: list[str] = []
    categories = split_csv(args.categories)
    publish_fields = split_csv(args.publish_fields)

    if args.provider_profile not in SIGNED_PROVIDER_PROFILES:
        blockers.append(f"signed_provider_profile_invalid:{args.provider_profile!r}")
    if args.model != SIGNED_MODEL:
        blockers.append(f"signed_model_invalid:{args.model!r}")

    if not categories:
        blockers.append("categories_missing")
    seen: set[str] = set()
    for category in categories:
        if category not in APPROVED_CATEGORIES:
            blockers.append(f"category_not_signed:{category}")
        if category in seen:
            blockers.append(f"category_duplicate:{category}")
        seen.add(category)

    if args.min_cases_per_category < 20 or args.min_cases_per_category > 50:
        blockers.append(f"min_cases_per_category_out_of_bounds:{args.min_cases_per_category}")
    if args.max_cases_per_category < 20 or args.max_cases_per_category > 50:
        blockers.append(f"max_cases_per_category_out_of_bounds:{args.max_cases_per_category}")
    if args.min_cases_per_category > args.max_cases_per_category:
        blockers.append("case_count_min_exceeds_max")
    if args.max_total_cases < 100 or args.max_total_cases > 200:
        blockers.append(f"max_total_cases_out_of_bounds:{args.max_total_cases}")
    if categories and len(categories) * args.min_cases_per_category > args.max_total_cases:
        blockers.append("max_total_cases_below_signed_category_minimum")

    planned_case_count = 0
    if categories:
        planned_case_count = min(args.max_cases_per_category, args.max_total_cases // len(categories))
        if planned_case_count < args.min_cases_per_category:
            blockers.append("planned_case_count_below_category_minimum")

    if args.output_root != SIGNED_OUTPUT_ROOT:
        blockers.append(f"output_root_not_signed:{args.output_root}")
    output_text = str(args.output_root).lower()
    for indicator in RAW_PATH_INDICATORS:
        if indicator in output_text:
            blockers.append(f"raw_path_indicator_in_output_root:{indicator}")
    if args.schema != SIGNED_SCHEMA:
        blockers.append(f"schema_path_not_signed:{args.schema}")

    if set(publish_fields) != set(SIGNED_PUBLISH_FIELDS):
        blockers.append("publish_fields_do_not_match_signed_schema")
    for field in publish_fields:
        normalized = normalize_field(field)
        if normalized in FORBIDDEN_FIELD_NAMES:
            blockers.append(f"forbidden_publish_field:{field}")

    if not args.compact_sanitized_only:
        blockers.append("compact_sanitized_only_required")
    for flag_name in ["no_raw_trace", "no_raw_payload", "no_candidate_jsonl", "no_scorer"]:
        if getattr(args, flag_name) is not True:
            blockers.append(f"{flag_name}_required")

    if args.execute_approved_source and not (args.dry_run or args.plan_only):
        blockers.append("execution_path_not_implemented_in_this_commit")
    if not (args.dry_run or args.plan_only or args.execute_approved_source):
        blockers.append("dry_run_or_plan_only_required_without_execution_approval")
    return blockers, categories, publish_fields, planned_case_count


def check(args: argparse.Namespace) -> dict[str, Any]:
    blockers, categories, publish_fields, planned_case_count = validate_args(args)
    approved_source_checker_passed = False
    after_source_matrix_checker_passed = False

    if not args.skip_preflight_checks:
        approved_source_checker_passed, error, _ = run_json_checker(
            ["scripts/check_rashe_source_real_trace_approved.py", "--compact", "--strict"]
        )
        if error:
            blockers.append(f"approved_source_checker_failed:{error}")
        after_source_matrix_checker_passed, error, _ = run_json_checker(
            ["scripts/check_rashe_approval_packet_review_matrix_after_source_approval.py", "--compact", "--strict"]
        )
        if error:
            blockers.append(f"after_source_matrix_checker_failed:{error}")
    else:
        approved_source_checker_passed = True
        after_source_matrix_checker_passed = True

    compact_plans = [build_compact_plan(category, planned_case_count) for category in categories if category in APPROVED_CATEGORIES]
    try:
        schema = load_json(args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        schema = {}
        blockers.append(f"schema_load_failed:{exc}")
    if schema:
        for artifact in compact_plans:
            blockers.extend(validate_schema_artifact(schema, artifact))

    return {
        "report_scope": "rashe_source_diagnostic_compact_plan",
        "provider_profile": args.provider_profile,
        "model": args.model,
        "categories": categories,
        "min_cases_per_category": args.min_cases_per_category,
        "max_cases_per_category": args.max_cases_per_category,
        "planned_case_count_per_category": planned_case_count,
        "max_total_cases": args.max_total_cases,
        "output_root": str(args.output_root),
        "schema_path": str(args.schema),
        "publish_fields": publish_fields,
        "dry_run": args.dry_run,
        "plan_only": args.plan_only,
        "execute_requested": args.execute_approved_source,
        "provider_call_executed": False,
        "api_key_read": False,
        "diagnostic_written": False,
        "approved_source_checker_passed": approved_source_checker_passed,
        "after_source_matrix_checker_passed": after_source_matrix_checker_passed,
        "raw_payload_tracked_count": 0,
        "forbidden_field_violation_count": 0,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "compact_artifact_plan": compact_plans,
        "rashe_source_diagnostic_compact_plan_passed": not blockers,
        "blockers": blockers,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-profile", default="Chuangzhi/Novacode")
    parser.add_argument("--model", default=SIGNED_MODEL)
    parser.add_argument("--categories", default=",".join(APPROVED_CATEGORIES))
    parser.add_argument("--min-cases-per-category", type=int, default=20)
    parser.add_argument("--max-cases-per-category", type=int, default=50)
    parser.add_argument("--max-total-cases", type=int, default=200)
    parser.add_argument("--output-root", type=Path, default=SIGNED_OUTPUT_ROOT)
    parser.add_argument("--schema", type=Path, default=SIGNED_SCHEMA)
    parser.add_argument("--compact-sanitized-only", action="store_true", default=True)
    parser.add_argument("--publish-fields", default=",".join(SIGNED_PUBLISH_FIELDS))
    parser.add_argument("--no-raw-trace", action="store_true", default=True)
    parser.add_argument("--no-raw-payload", action="store_true", default=True)
    parser.add_argument("--no-candidate-jsonl", action="store_true", default=True)
    parser.add_argument("--no-scorer", action="store_true", default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--execute-approved-source", action="store_true")
    parser.add_argument("--skip-preflight-checks", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    summary = check(args)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_source_diagnostic_compact_plan_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
