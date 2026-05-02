#!/usr/bin/env python3
"""Signed provider/source client factory for RASHE compact diagnostics.

The factory is importable and safe for dry-run validation. It does not read
credentials on import or factory construction. Real execution must still provide
an approved source-case provider and provider transport; otherwise the returned
client fails closed with ``source_case_provider_missing`` or
``provider_endpoint_missing`` until signed endpoint configuration is present.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
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
SIGNED_PROVIDER_PROFILE_WITH_MODEL = "Chuangzhi/Novacode gpt-4.1"
SIGNED_MODEL = "gpt-4.1"
SIGNED_CASES_PER_CATEGORY = 20
SIGNED_TOTAL_CASES = 160
SIGNED_OUTPUT_ROOT = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact"
SIGNED_SCHEMA_PATH = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json"
SOURCE_CASE_PROVIDER_KEYS = ("source_case_provider", "case_provider")
PROVIDER_TRANSPORT_KEYS = ("provider_transport", "source_provider_transport")
PROVIDER_TRANSPORT_APPROVED_CHECKER = "scripts/check_rashe_provider_transport_approved.py"
APPROVED_PROVIDER_KEY_ENV_VARS = ("CHUANGZHI_API_KEY", "NOVACODE_API_KEY")
APPROVED_PROVIDER_ENDPOINT_ENV_VARS = ("CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT")
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
SourceCaseProvider = Callable[[dict[str, Any]], list[dict[str, Any]]]
ProviderTransport = Callable[[dict[str, Any]], dict[str, Any] | None]
ProviderClient = Callable[[dict[str, Any]], dict[str, Any]]


class SourceProviderClientError(RuntimeError):
    """Fail-closed provider client error whose message is an auditable blocker."""


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
            if name in {"forbidden_fields", "failure_buckets"} or name in SOURCE_CASE_PROVIDER_KEYS or name in PROVIDER_TRANSPORT_KEYS:
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


def _callable_from_request(request: dict[str, Any], keys: tuple[str, ...]) -> Callable[..., Any] | None:
    for key in keys:
        value = request.get(key)
        if callable(value):
            return value
    return None


def _provider_transport_approved() -> None:
    result = subprocess.run(
        [sys.executable, PROVIDER_TRANSPORT_APPROVED_CHECKER, "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SourceProviderClientError("provider_transport_not_approved")


def _execution_endpoint(audit: dict[str, bool]) -> str:
    for env_name in APPROVED_PROVIDER_ENDPOINT_ENV_VARS:
        value = os.environ.get(env_name)
        if value:
            audit["endpoint_read"] = True
            lowered = value.lower()
            if not lowered.startswith("https://"):
                raise SourceProviderClientError("provider_endpoint_not_https")
            for indicator in RAW_VALUE_INDICATORS:
                if indicator in lowered:
                    raise SourceProviderClientError("provider_endpoint_forbidden_raw_indicator")
            return value
    raise SourceProviderClientError("provider_endpoint_missing")


def _execution_env_key(audit: dict[str, bool]) -> str:
    for env_name in APPROVED_PROVIDER_KEY_ENV_VARS:
        value = os.environ.get(env_name)
        if value:
            audit["api_key_read"] = True
            return value
    raise SourceProviderClientError("provider_key_missing")


def _http_post_json(endpoint: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # nosec B310 - endpoint must be signed by environment.
        data = response.read()
    parsed = json.loads(data.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise SourceProviderClientError("provider_transport_response_not_object")
    return parsed


def _build_env_only_provider_transport(audit: dict[str, bool]) -> ProviderTransport:
    _provider_transport_approved()

    def transport(request: dict[str, Any]) -> dict[str, Any]:
        hits = _forbidden_hits(request)
        if hits:
            raise SourceProviderClientError("provider_transport_request_forbidden_field:" + ";".join(hits))
        for flag in [
            "raw_payload_capture_authorized",
            "raw_trace_capture_authorized",
            "candidate_generation_authorized",
            "scorer_authorized",
            "performance_evidence",
        ]:
            if request.get(flag) is not False:
                raise SourceProviderClientError(f"provider_transport_{flag}_not_false")
        if request.get("provider_profile") != SIGNED_PROVIDER_PROFILE:
            raise SourceProviderClientError("provider_transport_profile_not_signed")
        if request.get("model") != SIGNED_MODEL:
            raise SourceProviderClientError("provider_transport_model_not_signed")
        endpoint = _execution_endpoint(audit)
        api_key = _execution_env_key(audit)
        response = _http_post_json(
            endpoint,
            api_key,
            {
                "category": request["category"],
                "ordinal": request["ordinal"],
                "provider_profile": SIGNED_PROVIDER_PROFILE,
                "model": SIGNED_MODEL,
                "compact_sanitized_only": True,
            },
        )
        return response

    return transport


def validate_factory_request(request: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if request.get("provider_profile") not in {SIGNED_PROVIDER_PROFILE, SIGNED_PROVIDER_PROFILE_WITH_MODEL}:
        blockers.append(f"provider_client_profile_not_signed:{request.get('provider_profile')!r}")
    if request.get("model") != SIGNED_MODEL:
        blockers.append(f"provider_client_model_not_signed:{request.get('model')!r}")
    if request.get("categories") != list(APPROVED_CATEGORIES):
        blockers.append("provider_client_categories_not_signed")
    if request.get("case_count_per_category") != SIGNED_CASES_PER_CATEGORY:
        blockers.append(f"provider_client_case_count_per_category_not_signed:{request.get('case_count_per_category')!r}")
    if request.get("max_total_cases") != SIGNED_TOTAL_CASES:
        blockers.append(f"provider_client_max_total_cases_not_signed:{request.get('max_total_cases')!r}")
    if _norm_path(str(request.get("output_root") or "")) != SIGNED_OUTPUT_ROOT:
        blockers.append(f"provider_client_output_root_not_signed:{request.get('output_root')!r}")
    if _norm_path(str(request.get("schema_path") or "")) != SIGNED_SCHEMA_PATH:
        blockers.append(f"provider_client_schema_path_not_signed:{request.get('schema_path')!r}")
    for flag in [
        "candidate_generation_authorized",
        "scorer_authorized",
        "performance_evidence",
        "raw_payload_capture_authorized",
        "raw_trace_capture_authorized",
    ]:
        if request.get(flag) is not False:
            blockers.append(f"provider_client_forbidden_flag_not_false:{flag}:{request.get(flag)!r}")
    if request.get("compact_sanitized_only") is not True:
        blockers.append("provider_client_compact_sanitized_only_not_true")
    blockers.extend(f"provider_client_forbidden_request_field:{hit}" for hit in _forbidden_hits(request))
    return blockers


def _validate_category_request(category_request: dict[str, Any]) -> str:
    if not isinstance(category_request, dict):
        raise SourceProviderClientError("source_category_request_not_object")
    hits = _forbidden_hits(category_request)
    if hits:
        raise SourceProviderClientError("source_category_request_forbidden_field:" + ";".join(hits))
    category = category_request.get("category")
    if category not in APPROVED_CATEGORIES:
        raise SourceProviderClientError(f"source_category_not_signed:{category!r}")
    if category_request.get("case_count") != SIGNED_CASES_PER_CATEGORY:
        raise SourceProviderClientError(f"source_category_case_count_not_signed:{category_request.get('case_count')!r}")
    if category_request.get("provider_profile") not in {SIGNED_PROVIDER_PROFILE, SIGNED_PROVIDER_PROFILE_WITH_MODEL}:
        raise SourceProviderClientError("source_category_provider_profile_not_signed")
    if category_request.get("model") != SIGNED_MODEL:
        raise SourceProviderClientError("source_category_model_not_signed")
    for flag in [
        "compact_sanitized_only",
    ]:
        if category_request.get(flag) is not True:
            raise SourceProviderClientError(f"source_category_{flag}_not_true")
    for flag in [
        "raw_payload_capture_authorized",
        "raw_trace_capture_authorized",
        "candidate_generation_authorized",
        "scorer_authorized",
        "performance_evidence",
    ]:
        if category_request.get(flag) is not False:
            raise SourceProviderClientError(f"source_category_{flag}_not_false")
    return str(category)


def _validate_cases(cases: Any, category: str) -> list[dict[str, Any]]:
    if not isinstance(cases, list):
        raise SourceProviderClientError("source_case_provider_output_not_list")
    if len(cases) != SIGNED_CASES_PER_CATEGORY:
        raise SourceProviderClientError(f"source_case_count_not_signed:{len(cases)}")
    sanitized_cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise SourceProviderClientError(f"source_case_not_object:{index}")
        hits = _forbidden_hits(case)
        if hits:
            raise SourceProviderClientError("source_case_forbidden_field:" + ";".join(hits))
        extra = set(case) - {"category", "ordinal", "prompt_family", "compact_hash"}
        if extra:
            raise SourceProviderClientError("source_case_extra_field:" + ",".join(sorted(extra)))
        if case.get("category", category) != category:
            raise SourceProviderClientError(f"source_case_category_mismatch:{case.get('category')!r}:{category}")
        sanitized_cases.append({"category": category, "ordinal": int(case.get("ordinal", index))})
    return sanitized_cases


def _transport_failure_buckets(result: dict[str, Any] | None) -> dict[str, int]:
    if result is None:
        return {bucket: 0 for bucket in FAILURE_BUCKETS}
    if not isinstance(result, dict):
        raise SourceProviderClientError("provider_transport_result_not_object")
    hits = _forbidden_hits(result)
    if hits:
        raise SourceProviderClientError("provider_transport_result_forbidden_field:" + ";".join(hits))
    extra = set(result) - {"failure_bucket", "failure_bucket_counts"}
    if extra:
        raise SourceProviderClientError("provider_transport_result_extra_field:" + ",".join(sorted(extra)))
    counts = {bucket: 0 for bucket in FAILURE_BUCKETS}
    if result.get("failure_bucket") is not None:
        bucket = str(result["failure_bucket"])
        if bucket not in counts:
            raise SourceProviderClientError(f"provider_transport_failure_bucket_not_signed:{bucket}")
        counts[bucket] += 1
    if result.get("failure_bucket_counts") is not None:
        bucket_counts = result["failure_bucket_counts"]
        if not isinstance(bucket_counts, dict):
            raise SourceProviderClientError("provider_transport_failure_bucket_counts_not_object")
        if set(bucket_counts) - set(FAILURE_BUCKETS):
            raise SourceProviderClientError("provider_transport_failure_bucket_counts_extra_key")
        for bucket, count in bucket_counts.items():
            value = int(count or 0)
            if value < 0:
                raise SourceProviderClientError("provider_transport_failure_bucket_count_negative")
            counts[bucket] += value
    return counts


def build_chuangzhi_novacode_source_provider_client(request: dict[str, Any]) -> ProviderClient:
    """Build the signed source provider client for compact diagnostics.

    The returned client remains fail-closed until the request carries both a
    sanitized source-case provider and a provider transport callable. This keeps
    imports/dry-runs key-free and prevents accidental raw payload capture.
    """

    blockers = validate_factory_request(request)
    if blockers:
        raise SourceProviderClientError(";".join(blockers))
    source_case_provider = _callable_from_request(request, SOURCE_CASE_PROVIDER_KEYS)
    provider_transport = _callable_from_request(request, PROVIDER_TRANSPORT_KEYS)
    audit = {"api_key_read": False, "endpoint_read": False}

    def client(category_request: dict[str, Any]) -> dict[str, Any]:
        category = _validate_category_request(category_request)
        if source_case_provider is None:
            raise SourceProviderClientError("source_case_provider_missing")
        active_provider_transport = provider_transport
        if active_provider_transport is None:
            active_provider_transport = _build_env_only_provider_transport(audit)
        cases = _validate_cases(
            source_case_provider(
                {
                    "category": category,
                    "case_count": SIGNED_CASES_PER_CATEGORY,
                    "compact_sanitized_only": True,
                    "raw_payload_capture_authorized": False,
                    "raw_trace_capture_authorized": False,
                }
            ),
            category,
        )
        aggregate = {bucket: 0 for bucket in FAILURE_BUCKETS}
        try:
            for case in cases:
                result = active_provider_transport(
                    {
                        "category": category,
                        "ordinal": case["ordinal"],
                        "provider_profile": SIGNED_PROVIDER_PROFILE,
                        "model": SIGNED_MODEL,
                        "compact_sanitized_only": True,
                        "raw_payload_capture_authorized": False,
                        "raw_trace_capture_authorized": False,
                        "candidate_generation_authorized": False,
                        "scorer_authorized": False,
                        "performance_evidence": False,
                    }
                )
                for bucket, count in _transport_failure_buckets(result).items():
                    aggregate[bucket] += count
        finally:
            client.api_key_read = audit["api_key_read"]  # type: ignore[attr-defined]
            client.endpoint_read = audit["endpoint_read"]  # type: ignore[attr-defined]
        return {
            "category": category,
            "case_count": SIGNED_CASES_PER_CATEGORY,
            "provider_call_count": len(cases),
            "failure_bucket_counts": aggregate,
            "raw_payload_tracked_count": 0,
            "forbidden_field_violation_count": 0,
            "candidate_generation_authorized": False,
            "scorer_authorized": False,
            "performance_evidence": False,
        }

    client.api_key_read = False  # type: ignore[attr-defined]
    client.endpoint_read = False  # type: ignore[attr-defined]
    return client
