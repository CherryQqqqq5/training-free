#!/usr/bin/env python3
"""Signed adapter boundary for RASHE compact source diagnostics.

The public adapter function is
``scripts.rashe_source_diagnostic_compact_adapter:run_compact_source_diagnostic``.
It validates the approved 8x20/160 request and converts sanitized source
counter records into the compact diagnostic schema. It never writes artifacts,
never logs credentials, and never returns raw trace/provider/case/scorer fields.
If the concrete approved source collector dependency is unavailable, execution
fails closed with ``source_execution_dependency_missing:...``.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from scripts.check_rashe_source_real_trace_approved import APPROVED_CATEGORIES, FAILURE_BUCKETS

SIGNED_PROVIDER_PROFILE = "Chuangzhi/Novacode"
SIGNED_PROVIDER_PROFILE_WITH_MODEL = "Chuangzhi/Novacode gpt-5.2"
SIGNED_MODEL = "gpt-5.2"
SIGNED_CASES_PER_CATEGORY = 20
SIGNED_TOTAL_CASES = 160
SIGNED_OUTPUT_ROOT = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact"
SIGNED_SCHEMA_PATH = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json"
DEPENDENCY_MODULE = "grc.bfcl.source_diagnostic_collector"
DEPENDENCY_FUNCTION = "collect_compact_source_diagnostics"
MISSING_DEPENDENCY_BLOCKER = f"source_execution_dependency_missing:{DEPENDENCY_MODULE}.{DEPENDENCY_FUNCTION}"
ALLOWED_COUNTER_FIELDS = {
    "category",
    "case_count",
    "provider_call_count",
    "failure_bucket_counts",
    "raw_payload_tracked_count",
    "forbidden_field_violation_count",
    "candidate_generation_authorized",
    "scorer_authorized",
    "performance_evidence",
}
FORBIDDEN_FIELD_NAMES = {
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


class SourceExecutionDependencyMissing(RuntimeError):
    """Raised when the concrete approved source collector is not present."""


def _norm_path(value: str | Path) -> str:
    return str(value).rstrip("/")


def _field_name(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _forbidden_hits(value: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            name = _field_name(str(key))
            path = f"{prefix}.{key}" if prefix else str(key)
            if name in {"forbidden_fields", "failure_buckets"}:
                continue
            if name in FORBIDDEN_FIELD_NAMES:
                hits.append(path)
            hits.extend(_forbidden_hits(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_forbidden_hits(child, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        for indicator in RAW_VALUE_INDICATORS:
            if indicator in lowered:
                hits.append(f"{prefix}:raw_indicator:{indicator}")
    return hits


def validate_request(request: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if request.get("provider_profile") not in {SIGNED_PROVIDER_PROFILE, SIGNED_PROVIDER_PROFILE_WITH_MODEL}:
        blockers.append(f"adapter_provider_profile_not_signed:{request.get('provider_profile')!r}")
    if request.get("model") != SIGNED_MODEL:
        blockers.append(f"adapter_model_not_signed:{request.get('model')!r}")
    if request.get("categories") != list(APPROVED_CATEGORIES):
        blockers.append("adapter_categories_not_signed")
    if request.get("case_count_per_category") != SIGNED_CASES_PER_CATEGORY:
        blockers.append(f"adapter_case_count_per_category_not_signed:{request.get('case_count_per_category')!r}")
    if request.get("max_total_cases") != SIGNED_TOTAL_CASES:
        blockers.append(f"adapter_max_total_cases_not_signed:{request.get('max_total_cases')!r}")
    if _norm_path(str(request.get("output_root") or "")) != SIGNED_OUTPUT_ROOT:
        blockers.append(f"adapter_output_root_not_signed:{request.get('output_root')!r}")
    if _norm_path(str(request.get("schema_path") or "")) != SIGNED_SCHEMA_PATH:
        blockers.append(f"adapter_schema_path_not_signed:{request.get('schema_path')!r}")
    for flag in [
        "candidate_generation_authorized",
        "scorer_authorized",
        "performance_evidence",
        "raw_payload_capture_authorized",
        "raw_trace_capture_authorized",
    ]:
        if request.get(flag) is not False:
            blockers.append(f"adapter_forbidden_flag_not_false:{flag}:{request.get(flag)!r}")
    if request.get("compact_sanitized_only") is not True:
        blockers.append("adapter_compact_sanitized_only_not_true")
    blockers.extend(f"adapter_forbidden_request_field:{hit}" for hit in _forbidden_hits(request))
    return blockers


def _validate_counter_record(record: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    extra = set(record) - ALLOWED_COUNTER_FIELDS
    for field in sorted(extra):
        blockers.append(f"adapter_counter_extra_field:{field}")
    blockers.extend(f"adapter_forbidden_counter_field:{hit}" for hit in _forbidden_hits(record))
    if record.get("category") not in APPROVED_CATEGORIES:
        blockers.append(f"adapter_counter_category_not_signed:{record.get('category')!r}")
    if record.get("case_count") != SIGNED_CASES_PER_CATEGORY:
        blockers.append(f"adapter_counter_case_count_not_signed:{record.get('case_count')!r}")
    provider_count = record.get("provider_call_count")
    if not isinstance(provider_count, int) or provider_count < 0 or provider_count > SIGNED_CASES_PER_CATEGORY:
        blockers.append(f"adapter_counter_provider_call_count_invalid:{provider_count!r}")
    if record.get("raw_payload_tracked_count", 0) != 0:
        blockers.append(f"adapter_counter_raw_payload_tracked_count_not_zero:{record.get('raw_payload_tracked_count')!r}")
    if record.get("forbidden_field_violation_count", 0) != 0:
        blockers.append(f"adapter_counter_forbidden_field_violation_count_not_zero:{record.get('forbidden_field_violation_count')!r}")
    for flag in ["candidate_generation_authorized", "scorer_authorized", "performance_evidence"]:
        if record.get(flag, False) is not False:
            blockers.append(f"adapter_counter_{flag}_not_false:{record.get(flag)!r}")
    buckets = record.get("failure_bucket_counts")
    if not isinstance(buckets, dict):
        blockers.append("adapter_counter_failure_bucket_counts_missing")
    elif set(buckets) != set(FAILURE_BUCKETS):
        blockers.append("adapter_counter_failure_bucket_counts_invalid")
    elif any((not isinstance(value, int) or value < 0) for value in buckets.values()):
        blockers.append("adapter_counter_failure_bucket_value_invalid")
    return blockers


def compact_artifact_from_sanitized_counter(record: dict[str, Any]) -> dict[str, Any]:
    blockers = _validate_counter_record(record)
    if blockers:
        raise ValueError(";".join(blockers))
    return {
        "schema_version": "rashe_source_diagnostic_compact_v0",
        "category": record["category"],
        "case_count": SIGNED_CASES_PER_CATEGORY,
        "provider_call_count": record["provider_call_count"],
        "raw_payload_tracked_count": 0,
        "forbidden_field_violation_count": 0,
        "failure_bucket_counts": {bucket: int(record["failure_bucket_counts"].get(bucket, 0)) for bucket in FAILURE_BUCKETS},
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }


def build_compact_artifacts_from_sanitized_counters(records: list[dict[str, Any]], request: dict[str, Any]) -> list[dict[str, Any]]:
    blockers = validate_request(request)
    if blockers:
        raise ValueError(";".join(blockers))
    if [record.get("category") for record in records] != list(APPROVED_CATEGORIES):
        raise ValueError("adapter_counter_categories_not_signed_order")
    artifacts = [compact_artifact_from_sanitized_counter(record) for record in records]
    if sum(artifact["case_count"] for artifact in artifacts) != SIGNED_TOTAL_CASES:
        raise ValueError("adapter_total_case_count_not_signed")
    return artifacts


def _load_source_collector():
    try:
        module = importlib.import_module(DEPENDENCY_MODULE)
    except Exception as exc:
        raise SourceExecutionDependencyMissing(MISSING_DEPENDENCY_BLOCKER) from exc
    collector = getattr(module, DEPENDENCY_FUNCTION, None)
    if not callable(collector):
        raise SourceExecutionDependencyMissing(MISSING_DEPENDENCY_BLOCKER)
    return collector


def run_compact_source_diagnostic(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Run the signed adapter boundary and return compact diagnostic artifacts.

    The concrete collector must return sanitized counter records only. This
    adapter then enforces schema shape, zero raw/leakage counters, and downstream
    false flags before returning artifacts to the runner for boundary-checked
    writing.
    """

    blockers = validate_request(request)
    if blockers:
        raise ValueError(";".join(blockers))
    collector = _load_source_collector()
    records = collector(dict(request))
    if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
        raise ValueError("adapter_collector_output_not_sanitized_counter_list")
    return build_compact_artifacts_from_sanitized_counters(records, request)
