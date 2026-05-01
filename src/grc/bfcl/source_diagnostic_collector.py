"""Compact source diagnostic collector boundary for RASHE Phase B.

This module intentionally does not discover or read credentials on import or in
unit-test paths. Real provider execution must inject an approved provider client
(or a future approved factory) through the request and must remain within the
signed 8x20/160 compact diagnostic contract.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

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
SIGNED_PROVIDER_PROFILE = "Chuangzhi/Novacode"
SIGNED_PROVIDER_PROFILE_WITH_MODEL = "Chuangzhi/Novacode gpt-5.2"
SIGNED_MODEL = "gpt-5.2"
SIGNED_CASES_PER_CATEGORY = 20
SIGNED_TOTAL_CASES = 160
SIGNED_OUTPUT_ROOT = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact"
SIGNED_SCHEMA_PATH = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json"
PROVIDER_CLIENT_REQUEST_KEYS = ("provider_client", "source_provider_client")
FORBIDDEN_FIELD_NAMES = {
    "raw_case_id",
    "case_id",
    "case id",
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
    "case id",
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
ALLOWED_RECORD_FIELDS = {
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
ProviderClient = Callable[[dict[str, Any]], dict[str, Any] | None]


class SourceDiagnosticCollectorError(RuntimeError):
    """Fail-closed collector error whose message is an auditable blocker."""


def _norm_path(value: str | Path) -> str:
    return str(value).rstrip("/")


def _field_name(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _forbidden_hits(value: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if callable(value):
        return hits
    if isinstance(value, dict):
        for key, child in value.items():
            name = _field_name(str(key))
            path = f"{prefix}.{key}" if prefix else str(key)
            if name in {"forbidden_fields", "failure_buckets"} or name in PROVIDER_CLIENT_REQUEST_KEYS:
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


def _request_provider_client(request: dict[str, Any]) -> ProviderClient | None:
    for key in PROVIDER_CLIENT_REQUEST_KEYS:
        client = request.get(key)
        if callable(client):
            return client
    return None


def validate_request(request: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if request.get("provider_profile") not in {SIGNED_PROVIDER_PROFILE, SIGNED_PROVIDER_PROFILE_WITH_MODEL}:
        blockers.append(f"collector_provider_profile_not_signed:{request.get('provider_profile')!r}")
    if request.get("model") != SIGNED_MODEL:
        blockers.append(f"collector_model_not_signed:{request.get('model')!r}")
    if request.get("categories") != list(APPROVED_CATEGORIES):
        blockers.append("collector_categories_not_signed")
    if request.get("case_count_per_category") != SIGNED_CASES_PER_CATEGORY:
        blockers.append(f"collector_case_count_per_category_not_signed:{request.get('case_count_per_category')!r}")
    if request.get("max_total_cases") != SIGNED_TOTAL_CASES:
        blockers.append(f"collector_max_total_cases_not_signed:{request.get('max_total_cases')!r}")
    if _norm_path(str(request.get("output_root") or "")) != SIGNED_OUTPUT_ROOT:
        blockers.append(f"collector_output_root_not_signed:{request.get('output_root')!r}")
    if _norm_path(str(request.get("schema_path") or "")) != SIGNED_SCHEMA_PATH:
        blockers.append(f"collector_schema_path_not_signed:{request.get('schema_path')!r}")
    for flag in [
        "candidate_generation_authorized",
        "scorer_authorized",
        "performance_evidence",
        "raw_payload_capture_authorized",
        "raw_trace_capture_authorized",
    ]:
        if request.get(flag) is not False:
            blockers.append(f"collector_forbidden_flag_not_false:{flag}:{request.get(flag)!r}")
    if request.get("compact_sanitized_only") is not True:
        blockers.append("collector_compact_sanitized_only_not_true")
    blockers.extend(f"collector_forbidden_request_field:{hit}" for hit in _forbidden_hits(request))
    return blockers


def _validate_failure_buckets(value: Any) -> dict[str, int]:
    if value is None:
        return {bucket: 0 for bucket in FAILURE_BUCKETS}
    if not isinstance(value, dict):
        raise SourceDiagnosticCollectorError("collector_failure_bucket_counts_not_object")
    if set(value) - set(FAILURE_BUCKETS):
        raise SourceDiagnosticCollectorError("collector_failure_bucket_counts_extra_key")
    buckets = {bucket: int(value.get(bucket, 0) or 0) for bucket in FAILURE_BUCKETS}
    if any(count < 0 for count in buckets.values()):
        raise SourceDiagnosticCollectorError("collector_failure_bucket_count_negative")
    return buckets


def _extract_counter_record(category: str, provider_result: dict[str, Any] | None) -> dict[str, Any]:
    if provider_result is None:
        raise SourceDiagnosticCollectorError("collector_provider_result_missing")
    result = provider_result
    if not isinstance(result, dict):
        raise SourceDiagnosticCollectorError("collector_provider_result_not_object")
    extra_forbidden = _forbidden_hits(result)
    if extra_forbidden:
        raise SourceDiagnosticCollectorError("collector_provider_result_forbidden_field:" + ";".join(extra_forbidden))
    sanitized = result.get("sanitized_counters") if isinstance(result.get("sanitized_counters"), dict) else result
    extra = set(sanitized) - ALLOWED_RECORD_FIELDS - {"sanitized_counters"}
    if extra:
        raise SourceDiagnosticCollectorError("collector_provider_result_extra_field:" + ",".join(sorted(extra)))
    record_category = sanitized.get("category", category)
    if record_category != category:
        raise SourceDiagnosticCollectorError(f"collector_category_mismatch:{record_category!r}:{category}")
    case_count = int(sanitized.get("case_count", SIGNED_CASES_PER_CATEGORY) or 0)
    if case_count != SIGNED_CASES_PER_CATEGORY:
        raise SourceDiagnosticCollectorError(f"collector_case_count_not_signed:{case_count}")
    provider_call_count = int(sanitized.get("provider_call_count", SIGNED_CASES_PER_CATEGORY) or 0)
    if provider_call_count < 0 or provider_call_count > SIGNED_CASES_PER_CATEGORY:
        raise SourceDiagnosticCollectorError(f"collector_provider_call_count_invalid:{provider_call_count}")
    raw_payload_tracked_count = int(sanitized.get("raw_payload_tracked_count", 0) or 0)
    if raw_payload_tracked_count != 0:
        raise SourceDiagnosticCollectorError(f"collector_raw_payload_tracked_count_not_zero:{raw_payload_tracked_count}")
    forbidden_field_violation_count = int(sanitized.get("forbidden_field_violation_count", 0) or 0)
    if forbidden_field_violation_count != 0:
        raise SourceDiagnosticCollectorError(f"collector_forbidden_field_violation_count_not_zero:{forbidden_field_violation_count}")
    for flag in ["candidate_generation_authorized", "scorer_authorized", "performance_evidence"]:
        if sanitized.get(flag, False) is not False:
            raise SourceDiagnosticCollectorError(f"collector_{flag}_not_false:{sanitized.get(flag)!r}")
    return {
        "category": category,
        "case_count": SIGNED_CASES_PER_CATEGORY,
        "provider_call_count": provider_call_count,
        "failure_bucket_counts": _validate_failure_buckets(sanitized.get("failure_bucket_counts")),
        "raw_payload_tracked_count": 0,
        "forbidden_field_violation_count": 0,
        "candidate_generation_authorized": False,
        "scorer_authorized": False,
        "performance_evidence": False,
    }


def collect_compact_source_diagnostics(request: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect signed compact source diagnostic counters.

    The concrete provider/source client must be injected as ``provider_client``
    or ``source_provider_client`` in the request. Without that client, this
    function fails closed with ``source_provider_client_missing``. The returned
    records are sanitized counters only and contain no raw request/response,
    trace path, case identity, scorer, candidate, or performance material.
    """

    blockers = validate_request(request)
    if blockers:
        raise SourceDiagnosticCollectorError(";".join(blockers))
    provider_client = _request_provider_client(request)
    if provider_client is None:
        raise SourceDiagnosticCollectorError("source_provider_client_missing")

    records: list[dict[str, Any]] = []
    for category in APPROVED_CATEGORIES:
        provider_result = provider_client(
            {
                "category": category,
                "case_count": SIGNED_CASES_PER_CATEGORY,
                "provider_profile": request["provider_profile"],
                "model": request["model"],
                "compact_sanitized_only": True,
                "raw_payload_capture_authorized": False,
                "raw_trace_capture_authorized": False,
                "candidate_generation_authorized": False,
                "scorer_authorized": False,
                "performance_evidence": False,
            }
        )
        records.append(_extract_counter_record(category, provider_result))
    if sum(record["case_count"] for record in records) != SIGNED_TOTAL_CASES:
        raise SourceDiagnosticCollectorError("collector_total_case_count_not_signed")
    return records
