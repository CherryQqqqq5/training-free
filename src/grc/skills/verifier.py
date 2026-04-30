"""Verifier for inert RASHE skeleton inputs and config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import VerifierReport, find_forbidden_fields, has_raw_case_id

REQUIRED_FALSE_CONFIG_KEYS = {
    "enabled",
    "runtime_behavior_authorized",
    "provider_calls_authorized",
    "source_collection_authorized",
    "scorer_authorized",
    "candidate_generation_authorized",
    "prompt_injection_authorized",
    "retry_authorized",
    "ruleengine_proxy_active_path_import_allowed",
}

REQUIRED_ZERO_CONFIG_KEYS = {
    "provider_call_count",
    "source_collection_call_count",
    "scorer_call_count",
    "candidate_call_count",
}


def verify_trace(trace: dict[str, Any]) -> VerifierReport:
    blockers: list[str] = []
    forbidden = find_forbidden_fields(trace)
    raw_case_id = has_raw_case_id(trace)
    path_hits = [hit for hit in forbidden if not (hit.endswith("case_id") or hit == "case_id")]
    if forbidden:
        blockers.append("forbidden_fields_present")
    for key in ["provider_call_count", "scorer_call_count", "source_collection_call_count"]:
        if trace.get(key, 0) != 0:
            blockers.append(f"{key}_not_zero")
    return VerifierReport(
        verifier_passed=not blockers,
        blockers=tuple(blockers),
        forbidden_field_violation_count=len(forbidden),
        path_indicator_violation_count=len(path_hits),
        raw_case_id_rejected_count=1 if raw_case_id else 0,
        case_hash_allowed_count=1 if trace.get("case_hash") and not raw_case_id else 0,
        provider_call_count=int(trace.get("provider_call_count") or 0),
        scorer_call_count=int(trace.get("scorer_call_count") or 0),
        source_collection_call_count=int(trace.get("source_collection_call_count") or 0),
    )


def verify_runtime_config(config: dict[str, Any]) -> VerifierReport:
    blockers: list[str] = []
    for key in REQUIRED_FALSE_CONFIG_KEYS:
        if config.get(key) is not False:
            blockers.append(f"{key}_not_false")
    for key in REQUIRED_ZERO_CONFIG_KEYS:
        if int(config.get(key) or 0) != 0:
            blockers.append(f"{key}_not_zero")
    manifest = config.get("skillbank_manifest_path")
    if not isinstance(manifest, str) or not manifest:
        blockers.append("skillbank_manifest_path_missing")
    forbidden = find_forbidden_fields(config)
    if forbidden:
        blockers.append("forbidden_fields_present")
    return VerifierReport(
        verifier_passed=not blockers,
        blockers=tuple(blockers),
        forbidden_field_violation_count=len(forbidden),
        provider_call_count=int(config.get("provider_call_count") or 0),
        scorer_call_count=int(config.get("scorer_call_count") or 0),
        source_collection_call_count=int(config.get("source_collection_call_count") or 0),
        candidate_generation_authorized=bool(config.get("candidate_generation_authorized")),
    )


def load_simple_yaml(path: Path) -> dict[str, Any]:
    """Load the flat runtime config without requiring PyYAML."""
    data: dict[str, Any] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"unsupported config line: {raw_line}")
        key, value = line.split(":", 1)
        data[key.strip()] = _parse_scalar(value.strip())
    return data


def _parse_scalar(value: str) -> Any:
    value = value.strip().strip(chr(34) + chr(39))
    if value.lower() == "false":
        return False
    if value.lower() == "true":
        return True
    if value.isdigit():
        return int(value)
    return value
