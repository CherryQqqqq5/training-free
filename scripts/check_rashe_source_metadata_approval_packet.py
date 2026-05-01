#!/usr/bin/env python3
"""Validate the RASHE source metadata approval packet.

This gate signs the compact sanitized metadata contract only. It does not check
for or require the metadata root to exist, and it does not authorize provider
transport, source diagnostics, candidate generation, scorer execution, or
performance/Huawei claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_metadata_approval_packet.json")
DEFAULT_SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_source_metadata_compact.schema.json")
SIGNED_METADATA_ROOT = "outputs/artifacts/stage1_bfcl_acceptance/approved_source_metadata_compact/"
SIGNED_OUTPUT_ROOT = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/"
SIGNED_SCHEMA_PATH = "outputs/artifacts/stage1_bfcl_acceptance/rashe_source_metadata_compact.schema.json"
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
PROMPT_FAMILY_TAXONOMY = (
    "hallucination_abstention",
    "irrelevance_abstention",
    "long_context_state_tracking",
    "memory_retrieval_required",
    "multi_turn_missing_function",
    "multi_turn_missing_parameter",
    "multi_turn_state_tracking",
    "web_search_required",
)
CATEGORY_PROMPT_FAMILY = {
    "agentic_web_search": "web_search_required",
    "agentic_memory": "memory_retrieval_required",
    "multi_turn_base": "multi_turn_state_tracking",
    "multi_turn_long_context": "long_context_state_tracking",
    "multi_turn_miss_param": "multi_turn_missing_parameter",
    "multi_turn_miss_func": "multi_turn_missing_function",
    "hallucination": "hallucination_abstention",
    "irrelevance": "irrelevance_abstention",
}
SOURCE_FAMILY_ID_TAXONOMY = (
    "agentic_web",
    "agentic_memory",
    "multi_turn_workflow",
    "abstention_safety",
)
CATEGORY_SOURCE_FAMILY_ID = {
    "agentic_web_search": "agentic_web",
    "agentic_memory": "agentic_memory",
    "multi_turn_base": "multi_turn_workflow",
    "multi_turn_long_context": "multi_turn_workflow",
    "multi_turn_miss_param": "multi_turn_workflow",
    "multi_turn_miss_func": "multi_turn_workflow",
    "hallucination": "abstention_safety",
    "irrelevance": "abstention_safety",
}
ALLOWED_METADATA_FIELDS = ("category", "ordinal", "prompt_family", "source_nonce", "source_family_id")
OUTPUT_MANIFEST_FIELDS = ("category", "ordinal", "prompt_family", "compact_source_hash")
FORBIDDEN_FIELDS = (
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
    "dev_manifest",
    "holdout_manifest",
    "full_manifest",
    "candidate_jsonl",
    "performance_metric",
)
REQUIRED_FALSE_FIELDS = (
    "metadata_root_prepared",
    "metadata_generated",
    "source_input_manifests_generated",
    "provider_transport_authorized",
    "source_diagnostic_execution_authorized",
    "raw_trace_capture_authorized",
    "raw_payload_capture_authorized",
    "candidate_generation_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
)
ZERO_FIELDS = (
    "candidate_call_count",
    "scorer_call_count",
    "provider_transport_call_count",
    "source_diagnostic_run_count",
    "raw_payload_tracked_count",
    "forbidden_field_violation_count",
)
NO_LEAKAGE_FALSE_FIELDS = (
    "raw_case_id_used",
    "raw_prompt_used",
    "gold_used",
    "expected_used",
    "reference_used",
    "scorer_diff_used",
    "candidate_output_used",
    "repair_output_used",
    "feedback_used",
    "holdout_feedback_used",
    "full_suite_feedback_used",
    "raw_trace_committed",
    "provider_payload_used",
    "nonce_to_raw_mapping_committed",
)
RAW_PATH_INDICATORS = (
    "raw_trace",
    "raw-trace",
    "raw_payload",
    "raw-payload",
    "raw_prompt",
    "raw-prompt",
    "case_id",
    "case-id",
    "provider_payload",
    "provider-payload",
    "scorer_diff",
    "candidate_output",
    "gold",
    "expected",
    "reference",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _norm_path(value: str) -> str:
    return value.rstrip("/") + "/" if value else ""


def raw_path_hits(value: Any, prefix: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            hits.extend(raw_path_hits(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(raw_path_hits(child, f"{prefix}[{index}]"))
    elif isinstance(value, str):
        lowered = value.lower()
        for indicator in RAW_PATH_INDICATORS:
            if indicator in lowered:
                hits.append(f"{prefix}:{indicator}")
    return hits


def validate_packet(packet: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    required_values = {
        "approval_packet_kind": "source_metadata_compact",
        "approval_status": "approved",
        "authorized": True,
        "approved_metadata_root_path": SIGNED_METADATA_ROOT,
        "downstream_output_manifest_root": SIGNED_OUTPUT_ROOT,
        "metadata_schema_path": SIGNED_SCHEMA_PATH,
        "records_per_category": 20,
        "total_record_count": 160,
    }
    for key, expected in required_values.items():
        if packet.get(key) != expected:
            blockers.append(f"packet_{key}_invalid:{packet.get(key)!r}")
    for path_key in ["approved_metadata_root_path", "downstream_output_manifest_root"]:
        value = str(packet.get(path_key) or "")
        if not value.startswith("outputs/artifacts/stage1_bfcl_acceptance/"):
            blockers.append(f"packet_{path_key}_outside_signed_artifact_dir:{value!r}")
        if raw_path_hits({path_key: value}):
            blockers.append(f"packet_{path_key}_raw_path_indicator:{value!r}")

    if packet.get("approved_categories") != list(APPROVED_CATEGORIES):
        blockers.append("packet_approved_categories_invalid")
    if packet.get("allowed_metadata_fields") != list(ALLOWED_METADATA_FIELDS):
        blockers.append("packet_allowed_metadata_fields_invalid")
    if packet.get("output_manifest_fields") != list(OUTPUT_MANIFEST_FIELDS):
        blockers.append("packet_output_manifest_fields_invalid")
    for field in packet.get("allowed_metadata_fields") or []:
        if field in FORBIDDEN_FIELDS:
            blockers.append(f"packet_allowed_metadata_field_forbidden:{field}")
    for field in packet.get("output_manifest_fields") or []:
        if field in FORBIDDEN_FIELDS:
            blockers.append(f"packet_output_manifest_field_forbidden:{field}")

    ordinal_policy = packet.get("ordinal_policy")
    if not isinstance(ordinal_policy, dict):
        blockers.append("packet_ordinal_policy_missing")
    else:
        expected_policy = {"base": 0, "min": 0, "max": 19, "continuous_required": True, "no_gaps_allowed": True}
        for key, expected in expected_policy.items():
            if ordinal_policy.get(key) != expected:
                blockers.append(f"packet_ordinal_policy_invalid:{key}:{ordinal_policy.get(key)!r}")

    if packet.get("prompt_family_taxonomy") != list(PROMPT_FAMILY_TAXONOMY):
        blockers.append("packet_prompt_family_taxonomy_invalid")
    if packet.get("category_prompt_family") != CATEGORY_PROMPT_FAMILY:
        blockers.append("packet_category_prompt_family_invalid")
    prompt_policy = packet.get("prompt_family_policy") or {}
    for key in ["controlled_taxonomy_only"]:
        if prompt_policy.get(key) is not True:
            blockers.append(f"packet_prompt_family_policy_not_true:{key}")
    for key in ["raw_prompt_summary_allowed", "task_text_allowed", "tool_parameter_text_allowed", "case_id_allowed"]:
        if prompt_policy.get(key) is not False:
            blockers.append(f"packet_prompt_family_policy_not_false:{key}")

    nonce_policy = packet.get("source_nonce_policy")
    if not isinstance(nonce_policy, dict):
        blockers.append("packet_source_nonce_policy_missing")
    else:
        if nonce_policy.get("required") is not True:
            blockers.append("packet_source_nonce_required_not_true")
        if int(nonce_policy.get("min_length") or 0) < 32:
            blockers.append("packet_source_nonce_min_length_too_small")
        if nonce_policy.get("high_entropy_random_required") is not True:
            blockers.append("packet_source_nonce_entropy_not_required")
        for key in [
            "case_id_derivation_allowed",
            "prompt_derivation_allowed",
            "gold_expected_reference_derivation_allowed",
            "trace_path_derivation_allowed",
            "provider_payload_derivation_allowed",
            "nonce_to_raw_case_mapping_tracked",
            "nonce_to_raw_case_mapping_committed",
        ]:
            if nonce_policy.get(key) is not False:
                blockers.append(f"packet_source_nonce_policy_not_false:{key}")
        if nonce_policy.get("future_selector_may_use_mapping_only_in_memory") is not True:
            blockers.append("packet_source_nonce_future_selector_memory_only_not_true")

    if packet.get("source_family_id_taxonomy") != list(SOURCE_FAMILY_ID_TAXONOMY):
        blockers.append("packet_source_family_id_taxonomy_invalid")
    if packet.get("category_source_family_id") != CATEGORY_SOURCE_FAMILY_ID:
        blockers.append("packet_category_source_family_id_invalid")
    family_policy = packet.get("source_family_id_policy") or {}
    if family_policy.get("allowed_in_metadata") is not True:
        blockers.append("packet_source_family_id_not_allowed_in_metadata")
    if family_policy.get("controlled_taxonomy_only") is not True:
        blockers.append("packet_source_family_id_taxonomy_not_required")
    if family_policy.get("taxonomy_values") != list(SOURCE_FAMILY_ID_TAXONOMY):
        blockers.append("packet_source_family_id_policy_taxonomy_values_invalid")
    if family_policy.get("category_mapping_required") is not True:
        blockers.append("packet_source_family_id_category_mapping_not_required")
    for key in ["allowed_in_output_manifest", "case_specific_information_allowed", "raw_text_allowed"]:
        if family_policy.get(key) is not False:
            blockers.append(f"packet_source_family_id_policy_not_false:{key}")

    forbidden = set(packet.get("forbidden_fields") or [])
    for field in FORBIDDEN_FIELDS:
        if field not in forbidden:
            blockers.append(f"packet_forbidden_field_missing:{field}")
    for key in REQUIRED_FALSE_FIELDS:
        if packet.get(key) is not False:
            blockers.append(f"packet_{key}_not_false:{packet.get(key)!r}")
    for key in ZERO_FIELDS:
        if int(packet.get(key, -1) or 0) != 0:
            blockers.append(f"packet_{key}_not_zero:{packet.get(key)!r}")
    no_leakage = packet.get("no_leakage_required")
    if not isinstance(no_leakage, dict):
        blockers.append("packet_no_leakage_required_missing")
    else:
        for key in NO_LEAKAGE_FALSE_FIELDS:
            if no_leakage.get(key) is not False:
                blockers.append(f"packet_no_leakage_field_not_false:{key}")
    return blockers


def validate_schema(schema: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if schema.get("title") != "RASHE Source Metadata Compact Record":
        blockers.append("schema_title_invalid")
    if schema.get("additionalProperties") is not False:
        blockers.append("schema_additional_properties_not_false")
    if schema.get("required") != list(ALLOWED_METADATA_FIELDS):
        blockers.append("schema_required_fields_invalid")
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    if props.get("category", {}).get("enum") != list(APPROVED_CATEGORIES):
        blockers.append("schema_category_enum_invalid")
    ordinal = props.get("ordinal", {})
    if ordinal.get("minimum") != 0 or ordinal.get("maximum") != 19:
        blockers.append("schema_ordinal_bounds_invalid")
    if props.get("prompt_family", {}).get("enum") != list(PROMPT_FAMILY_TAXONOMY):
        blockers.append("schema_prompt_family_enum_invalid")
    if int(props.get("source_nonce", {}).get("minLength") or 0) < 32:
        blockers.append("schema_source_nonce_min_length_too_small")
    source_family = props.get("source_family_id", {})
    if not source_family:
        blockers.append("schema_source_family_id_missing")
    elif source_family.get("enum") != list(SOURCE_FAMILY_ID_TAXONOMY):
        blockers.append("schema_source_family_id_enum_invalid")
    for field in props:
        if field not in ALLOWED_METADATA_FIELDS:
            blockers.append(f"schema_property_not_allowed:{field}")
        if field in FORBIDDEN_FIELDS:
            blockers.append(f"schema_property_forbidden:{field}")
    return blockers


def check(packet_path: Path = DEFAULT_PACKET, schema_path: Path = DEFAULT_SCHEMA) -> dict[str, Any]:
    packet = load_json(packet_path)
    schema = load_json(schema_path)
    blockers = validate_packet(packet)
    blockers.extend(validate_schema(schema))
    return {
        "report_scope": "rashe_source_metadata_approval_packet_check",
        "packet_path": str(packet_path),
        "schema_path": str(schema_path),
        "approval_status": packet.get("approval_status"),
        "authorized": packet.get("authorized"),
        "approved_metadata_root_path": packet.get("approved_metadata_root_path"),
        "downstream_output_manifest_root": packet.get("downstream_output_manifest_root"),
        "records_per_category": packet.get("records_per_category"),
        "total_record_count": packet.get("total_record_count"),
        "metadata_root_prepared": packet.get("metadata_root_prepared"),
        "metadata_generated": packet.get("metadata_generated"),
        "source_input_manifests_generated": packet.get("source_input_manifests_generated"),
        "provider_transport_authorized": packet.get("provider_transport_authorized"),
        "source_diagnostic_execution_authorized": packet.get("source_diagnostic_execution_authorized"),
        "candidate_generation_authorized": packet.get("candidate_generation_authorized"),
        "scorer_authorized": packet.get("scorer_authorized"),
        "performance_evidence": packet.get("performance_evidence"),
        "huawei_acceptance_ready": packet.get("huawei_acceptance_ready"),
        "rashe_source_metadata_approval_packet_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=DEFAULT_PACKET)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.packet, args.schema)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "rashe_source_metadata_approval_packet_check",
            "packet_path": str(args.packet),
            "schema_path": str(args.schema),
            "rashe_source_metadata_approval_packet_passed": False,
            "blockers": [f"metadata_approval_check_load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_source_metadata_approval_packet_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
