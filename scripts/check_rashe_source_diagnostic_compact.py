#!/usr/bin/env python3
"""Check compact RASHE source diagnostic artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

APPROVED_CATEGORIES = (
    "agentic_web_search",
    "agentic_memory",
    "multi_turn_base",
    "multi_turn_long_context",
    "multi_turn_miss_param",
    "multi_turn_miss_func",
    "hallucination",
    "irrelevance",
)
FAILURE_BUCKETS = (
    "answered_without_tool",
    "wrong_first_tool",
    "search_query_too_broad",
    "fetch_missing_after_search",
    "memory_not_retrieved",
    "memory_update_when_should_search",
    "multi_turn_state_lost",
    "invalid_tool_call_format",
    "parser_schema_failure",
    "final_answer_before_tool",
    "irrelevant_tool_call",
    "unsupported_hallucinated_answer",
)
SIGNED_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/")
SIGNED_CASE_COUNT = 20
ALLOWED_FIELDS = {
    "schema_version",
    "category",
    "case_count",
    "provider_call_count",
    "raw_payload_tracked_count",
    "forbidden_field_violation_count",
    "failure_bucket_counts",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
}
FORBIDDEN_FIELD_NAMES = {
    "raw_case_id",
    "case_id",
    "raw_prompt",
    "prompt",
    "prompt_text",
    "task_text",
    "tool_trace",
    "trace_path",
    "raw_trace",
    "raw_provider_payload",
    "provider_payload",
    "provider_response",
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
    "scorer_output",
    "performance_evidence_claim",
    "huawei_acceptance_claim",
}
RAW_VALUE_INDICATORS = (
    "raw_trace",
    "raw-trace",
    "raw_payload",
    "raw-payload",
    "case_id",
    "case-id",
    "provider_payload",
    "provider-payload",
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "candidate_output",
    "repair_output",
    "holdout_feedback",
    "full_suite_feedback",
)


def _field_name(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def forbidden_hits(value: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            name = _field_name(str(key))
            path = f"{prefix}.{key}" if prefix else str(key)
            if name in FORBIDDEN_FIELD_NAMES:
                hits.append(path)
            hits.extend(forbidden_hits(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(forbidden_hits(child, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        for indicator in RAW_VALUE_INDICATORS:
            if indicator in lowered:
                hits.append(f"{prefix}:raw_indicator:{indicator}")
    return hits


def load_artifact(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return None, [f"source_diagnostic_read_failed:{path}:{exc}"]
    except json.JSONDecodeError as exc:
        return None, [f"source_diagnostic_json_invalid:{path}:{exc}"]
    if not isinstance(data, dict):
        return None, [f"source_diagnostic_not_object:{path}"]
    return data, []


def check_artifact(path: Path, category: str) -> tuple[int, list[str]]:
    blockers: list[str] = []
    artifact, load_blockers = load_artifact(path)
    blockers.extend(load_blockers)
    if artifact is None:
        return 0, blockers
    if set(artifact) != ALLOWED_FIELDS:
        blockers.append(f"source_diagnostic_fields_do_not_match_allowlist:{category}")
    for field in sorted(set(artifact) - ALLOWED_FIELDS):
        blockers.append(f"source_diagnostic_extra_field:{category}:{field}")
    hits = forbidden_hits(artifact)
    blockers.extend(f"source_diagnostic_forbidden_field:{category}:{hit}" for hit in hits)
    if artifact.get("schema_version") != "rashe_source_diagnostic_compact_v0":
        blockers.append(f"source_diagnostic_schema_version_invalid:{category}:{artifact.get('schema_version')!r}")
    if artifact.get("category") != category:
        blockers.append(f"source_diagnostic_category_mismatch:{artifact.get('category')!r}:{category}")
    if artifact.get("case_count") != SIGNED_CASE_COUNT:
        blockers.append(f"source_diagnostic_case_count_not_signed:{category}:{artifact.get('case_count')!r}")
    provider_count = artifact.get("provider_call_count")
    if not isinstance(provider_count, int) or provider_count < 0 or provider_count > SIGNED_CASE_COUNT:
        blockers.append(f"source_diagnostic_provider_call_count_invalid:{category}:{provider_count!r}")
    for field in ["raw_payload_tracked_count", "forbidden_field_violation_count"]:
        if artifact.get(field) != 0:
            blockers.append(f"source_diagnostic_{field}_not_zero:{category}:{artifact.get(field)!r}")
    for field in ["candidate_generation_authorized", "scorer_authorized", "performance_evidence"]:
        if artifact.get(field) is not False:
            blockers.append(f"source_diagnostic_{field}_not_false:{category}:{artifact.get(field)!r}")
    buckets = artifact.get("failure_bucket_counts")
    if not isinstance(buckets, dict):
        blockers.append(f"source_diagnostic_failure_buckets_not_object:{category}")
    elif set(buckets) != set(FAILURE_BUCKETS):
        blockers.append(f"source_diagnostic_failure_bucket_keys_invalid:{category}")
    else:
        for bucket, value in buckets.items():
            if not isinstance(value, int) or value < 0:
                blockers.append(f"source_diagnostic_failure_bucket_value_invalid:{category}:{bucket}:{value!r}")
    return SIGNED_CASE_COUNT if artifact.get("case_count") == SIGNED_CASE_COUNT else 0, blockers


def check_root(root: Path = SIGNED_ROOT) -> dict[str, Any]:
    blockers: list[str] = []
    category_counts: dict[str, int] = {}
    if not root.exists():
        return {"category_counts": category_counts, "total_case_count": 0, "blockers": [f"source_diagnostic_root_missing:{root}"]}
    expected_files = {f"{category}.json" for category in APPROVED_CATEGORIES}
    actual_files = {path.name for path in root.iterdir() if path.is_file()}
    if actual_files != expected_files:
        blockers.append("source_diagnostic_files_not_exact_signed_set")
        for name in sorted(actual_files - expected_files):
            blockers.append(f"source_diagnostic_extra_file:{name}")
        for name in sorted(expected_files - actual_files):
            blockers.append(f"source_diagnostic_missing_file:{name}")
    for category in APPROVED_CATEGORIES:
        path = root / f"{category}.json"
        if not path.exists():
            category_counts[category] = 0
            continue
        count, artifact_blockers = check_artifact(path, category)
        category_counts[category] = count
        blockers.extend(artifact_blockers)
    return {"category_counts": category_counts, "total_case_count": sum(category_counts.values()), "blockers": blockers}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=SIGNED_ROOT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    result = check_root(args.root)
    summary = {
        "report_scope": "rashe_source_diagnostic_compact_check",
        "root": str(args.root),
        "categories": list(APPROVED_CATEGORIES),
        "case_count_per_category": SIGNED_CASE_COUNT,
        "category_counts": result["category_counts"],
        "total_case_count": result["total_case_count"],
        "failure_buckets": list(FAILURE_BUCKETS),
        "rashe_source_diagnostic_compact_passed": not result["blockers"],
        "blockers": result["blockers"],
    }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_source_diagnostic_compact_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
