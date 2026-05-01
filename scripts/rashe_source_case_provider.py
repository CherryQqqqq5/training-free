#!/usr/bin/env python3
"""Signed source-case provider boundary for RASHE compact diagnostics.

The provider returns sanitized descriptors only. It does not call providers,
read credentials, write diagnostics, or expose raw BFCL case identity/prompt
material. Real execution must supply approved compact source-input manifests
under the signed root; otherwise the callable fails closed with
``bfcl_source_inputs_missing``.
"""

from __future__ import annotations

import hashlib
import json
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
SIGNED_CASES_PER_CATEGORY = 20
SIGNED_TOTAL_CASES = 160
SIGNED_SOURCE_INPUT_ROOT = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact"
ALLOWED_INPUT_FIELDS = {"category", "ordinal", "prompt_family", "compact_source_hash"}
ALLOWED_OUTPUT_FIELDS = {"category", "ordinal", "prompt_family", "compact_hash"}
FORBIDDEN_FIELD_NAMES = {
    "raw_case_id",
    "case_id",
    "case id",
    "raw_prompt",
    "prompt",
    "prompt_text",
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
}
RAW_VALUE_INDICATORS = (
    "raw_trace",
    "raw-trace",
    "raw_payload",
    "raw-payload",
    "raw_prompt",
    "raw-prompt",
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


class SourceCaseProviderError(RuntimeError):
    """Fail-closed source-case provider error whose message is a blocker."""


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
            if name in {"source_input_root", "source_case_provider_fixture_mode", "forbidden_fields", "failure_buckets"}:
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


def _request_root(request: dict[str, Any]) -> Path:
    root = request.get("source_input_root", SIGNED_SOURCE_INPUT_ROOT)
    root_text = _norm_path(str(root))
    fixture_mode = request.get("source_case_provider_fixture_mode") is True
    if root_text != SIGNED_SOURCE_INPUT_ROOT and not fixture_mode:
        raise SourceCaseProviderError(f"source_case_provider_root_not_signed:{root_text}")
    return Path(root_text)


def validate_builder_request(request: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    categories = request.get("categories")
    if categories is not None and categories != list(APPROVED_CATEGORIES):
        blockers.append("source_case_provider_categories_not_signed")
    if request.get("case_count_per_category") not in {None, SIGNED_CASES_PER_CATEGORY}:
        blockers.append(f"source_case_provider_case_count_not_signed:{request.get('case_count_per_category')!r}")
    if request.get("max_total_cases") not in {None, SIGNED_TOTAL_CASES}:
        blockers.append(f"source_case_provider_total_count_not_signed:{request.get('max_total_cases')!r}")
    try:
        _request_root(request)
    except SourceCaseProviderError as exc:
        blockers.append(str(exc))
    blockers.extend(f"source_case_provider_forbidden_request_field:{hit}" for hit in _forbidden_hits(request))
    return blockers


def _category_path(root: Path, category: str) -> Path:
    jsonl_path = root / f"{category}.jsonl"
    if jsonl_path.exists():
        return jsonl_path
    return root / f"{category}.json"


def _load_category_records(root: Path, category: str) -> list[dict[str, Any]]:
    path = _category_path(root, category)
    if not path.exists():
        raise SourceCaseProviderError(f"bfcl_source_inputs_missing:{category}:{path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceCaseProviderError(f"source_case_provider_data_missing:{category}:{exc}") from exc
    try:
        if path.suffix == ".jsonl":
            records = [json.loads(line) for line in text.splitlines() if line.strip()]
        else:
            payload = json.loads(text)
            if isinstance(payload, dict):
                records = payload.get("records") or payload.get("cases") or []
            else:
                records = payload
    except json.JSONDecodeError as exc:
        raise SourceCaseProviderError(f"source_case_provider_data_invalid:{category}:{exc}") from exc
    if not isinstance(records, list):
        raise SourceCaseProviderError(f"source_case_provider_records_not_list:{category}")
    return records


def _stable_compact_hash(category: str, ordinal: int, prompt_family: str, compact_source_hash: str) -> str:
    material = json.dumps(
        {
            "namespace": "rashe_source_case_descriptor_v0",
            "category": category,
            "ordinal": ordinal,
            "prompt_family": prompt_family,
            "compact_source_hash": compact_source_hash,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def _sanitize_record(record: Any, category: str, index: int) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise SourceCaseProviderError(f"source_case_provider_record_not_object:{category}:{index}")
    hits = _forbidden_hits(record)
    if hits:
        raise SourceCaseProviderError("source_case_provider_forbidden_input_field:" + ";".join(hits))
    extra = set(record) - ALLOWED_INPUT_FIELDS
    if extra:
        raise SourceCaseProviderError("source_case_provider_input_extra_field:" + ",".join(sorted(extra)))
    if record.get("category") != category:
        raise SourceCaseProviderError(f"source_case_provider_category_mismatch:{record.get('category')!r}:{category}")
    try:
        ordinal = int(record.get("ordinal"))
    except (TypeError, ValueError) as exc:
        raise SourceCaseProviderError(f"source_case_provider_ordinal_invalid:{category}:{index}") from exc
    if ordinal != index:
        raise SourceCaseProviderError(f"source_case_provider_ordinal_not_signed:{category}:{ordinal}:{index}")
    prompt_family = str(record.get("prompt_family") or "")
    compact_source_hash = str(record.get("compact_source_hash") or "")
    if not prompt_family:
        raise SourceCaseProviderError(f"source_case_provider_prompt_family_missing:{category}:{index}")
    if not compact_source_hash:
        raise SourceCaseProviderError(f"source_case_provider_compact_source_hash_missing:{category}:{index}")
    output = {
        "category": category,
        "ordinal": ordinal,
        "prompt_family": prompt_family,
        "compact_hash": _stable_compact_hash(category, ordinal, prompt_family, compact_source_hash),
    }
    if set(output) != ALLOWED_OUTPUT_FIELDS:
        raise SourceCaseProviderError("source_case_provider_output_schema_invalid")
    output_hits = _forbidden_hits(output)
    if output_hits:
        raise SourceCaseProviderError("source_case_provider_output_forbidden_field:" + ";".join(output_hits))
    return output


def build_signed_source_case_provider(request: dict[str, Any]) -> SourceCaseProvider:
    """Return the signed source-case provider callable.

    Construction is dry-run safe and does not read source inputs. The returned
    callable reads only signed compact source-input manifests and returns exactly
    sanitized descriptors for one signed category.
    """

    blockers = validate_builder_request(request)
    if blockers:
        raise SourceCaseProviderError(";".join(blockers))
    root = _request_root(request)

    def source_case_provider(category_request: dict[str, Any]) -> list[dict[str, Any]]:
        hits = _forbidden_hits(category_request)
        if hits:
            raise SourceCaseProviderError("source_case_provider_category_request_forbidden_field:" + ";".join(hits))
        category = category_request.get("category")
        if category not in APPROVED_CATEGORIES:
            raise SourceCaseProviderError(f"source_case_provider_category_not_signed:{category!r}")
        if category_request.get("case_count") != SIGNED_CASES_PER_CATEGORY:
            raise SourceCaseProviderError(f"source_case_provider_case_count_not_signed:{category_request.get('case_count')!r}")
        if category_request.get("compact_sanitized_only") is not True:
            raise SourceCaseProviderError("source_case_provider_compact_sanitized_only_not_true")
        for flag in ["raw_payload_capture_authorized", "raw_trace_capture_authorized"]:
            if category_request.get(flag) is not False:
                raise SourceCaseProviderError(f"source_case_provider_{flag}_not_false")
        records = _load_category_records(root, str(category))
        if len(records) != SIGNED_CASES_PER_CATEGORY:
            raise SourceCaseProviderError(f"source_case_provider_count_not_signed:{category}:{len(records)}")
        return [_sanitize_record(record, str(category), index) for index, record in enumerate(records)]

    return source_case_provider
