#!/usr/bin/env python3
"""Diagnose clean-control source availability for explicit-obligation smoke.

This is an offline/read-only diagnostic. It reads the materialized explicit
obligation protocol, the memory-operation obligation audit, and existing source
traces. It never runs BFCL/model/scorer and never emits execution commands.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import scripts.build_explicit_obligation_executable_smoke_protocol as executable_builder

_map_record = executable_builder._map_record
from scripts.diagnose_explicit_obligation_baseline_dry_audit import _audit_record

DEFAULT_PROTOCOL = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_executable_smoke_protocol.json")
DEFAULT_MEMORY_AUDIT = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_obligation_audit.json")
DEFAULT_SOURCE_ROOT = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
DEFAULT_OUT = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/clean_control_source_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/clean_control_source_audit.md")
DEFAULT_CATEGORIES = ("memory_kv", "memory_rec_sum", "memory", "memory_vector")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _rows_from_protocol(protocol: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for key in keys:
        for item in _as_list(protocol.get(key)):
            if not isinstance(item, dict):
                continue
            identity = (
                str(item.get("audit_case_id") or item.get("source_audit_record_id") or ""),
                str(item.get("bfcl_case_id") or ""),
                str(item.get("trace_relative_path") or ""),
            )
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(item)
    return rows


def _memory_audit_records(memory_audit: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_key in ("candidate_records", "sample_candidates", "sample_rejections"):
        for item in _as_list(memory_audit.get(source_key)):
            if not isinstance(item, dict):
                continue
            rows.append({**item, "memory_audit_source_key": source_key})
    return rows


def _trace_relative_from_audit(item: dict[str, Any]) -> str:
    return str(item.get("trace_relative_path") or item.get("source_audit_record_pointer_debug_only") or "")


def _audit_index_by_trace(memory_audit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in _memory_audit_records(memory_audit):
        trace = _trace_relative_from_audit(item)
        if not trace:
            continue
        current = index.get(trace)
        if current is None or current.get("memory_audit_source_key") == "sample_candidates":
            index[trace] = item
    return index


def _memory_capable_trace_records(source_root: Path, categories: tuple[str, ...], audit_by_trace: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for category in categories:
        trace_dir = source_root / category / "baseline" / "traces"
        if not trace_dir.exists():
            continue
        for trace_path in sorted(trace_dir.glob("*.json")):
            trace_relative = str(trace_path.relative_to(source_root))
            audited = audit_by_trace.get(trace_relative, {})
            record = {
                "category": category,
                "trace_relative_path": trace_relative,
                "source_audit_record_id": audited.get("source_audit_record_id"),
                "audit_case_id": audited.get("candidate_id") or audited.get("source_audit_record_id") or trace_path.stem,
                "candidate_id": audited.get("candidate_id"),
                "memory_audit_source_key": audited.get("memory_audit_source_key"),
                "operation": audited.get("operation"),
                "operation_scope": audited.get("operation_scope"),
                "operation_cue": audited.get("operation_cue"),
                "rejection_reason": audited.get("rejection_reason"),
                "review_rejection_reason": audited.get("review_rejection_reason"),
                "policy_family": audited.get("policy_family"),
                "theory_class": audited.get("theory_class"),
                "memory_witness_strength": audited.get("memory_witness_strength"),
                "memory_postcondition_witness_present": audited.get("memory_postcondition_witness_present"),
                "memory_postcondition_witnesses": audited.get("memory_postcondition_witnesses"),
                "recommended_tools": audited.get("recommended_tools") or [],
                "called_memory_tools": audited.get("called_memory_tools") or [],
                "candidate_ready": audited.get("candidate_ready"),
                "risk_level": audited.get("risk_level"),
            }
            records.append(record)
    return records


def _bool_status(value: bool | None) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "unknown"


def _no_explicit_obligation(item: dict[str, Any]) -> bool | None:
    reason = str(item.get("rejection_reason") or item.get("review_rejection_reason") or "")
    operation = item.get("operation")
    recommended = _as_list(item.get("recommended_tools"))
    if reason == "no_memory_operation_intent":
        return True
    if item.get("candidate_ready") is True or item.get("policy_family") == "memory_operation_obligation":
        return False
    if operation == "retrieve" or recommended:
        return False
    if operation is None and not recommended:
        return True
    return None


def _no_hidden_state_dependency(item: dict[str, Any], no_explicit: bool | None) -> bool | None:
    if no_explicit is False:
        return False
    witnesses = _as_list(item.get("memory_postcondition_witnesses"))
    if item.get("memory_postcondition_witness_present") is True or witnesses:
        return False
    strength = item.get("memory_witness_strength")
    if strength in {"weak_lookup_witness", "empty_or_error_witness"}:
        return False
    if no_explicit is True:
        return True
    return None


def _protocol_mapping_by_trace(protocol: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows = _rows_from_protocol(
        protocol,
        "selected_positive_cases",
        "positive_selection_rejections",
        "selected_control_cases",
        "control_selection_rejections",
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for item in rows:
        trace = str(item.get("trace_relative_path") or "")
        if trace:
            out.setdefault(trace, []).append(item)
    return out


def _mapping_status(item: dict[str, Any], source_root: Path, mapping_by_trace: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    trace = str(item.get("trace_relative_path") or "")
    protocol_matches = [match for match in mapping_by_trace.get(trace, []) if match.get("bfcl_case_id")]
    protocol_case_ids = sorted({str(match.get("bfcl_case_id")) for match in protocol_matches})
    if len(protocol_case_ids) == 1:
        match = protocol_matches[0]
        return {
            "bfcl_case_id": protocol_case_ids[0],
            "prompt_match_count": match.get("prompt_match_count"),
            "mapping_status": "materialized_protocol_trace_index",
            "dependency_closure_ready": bool(match.get("dependency_closure_ready")),
            "generation_case_ids": match.get("generation_case_ids") or [],
            "missing_dependency_ids": match.get("missing_dependency_ids") or [],
            "mapping_evidence_available": True,
        }
    if len(protocol_case_ids) > 1:
        return {
            "bfcl_case_id": None,
            "prompt_match_count": len(protocol_case_ids),
            "mapping_status": "ambiguous_materialized_protocol_trace_index",
            "dependency_closure_ready": False,
            "generation_case_ids": [],
            "missing_dependency_ids": [],
            "mapping_evidence_available": True,
        }
    try:
        mapped = _map_record(item, source_root, "control")
    except Exception as exc:  # pragma: no cover - defensive for local BFCL import failures
        return {
            "bfcl_case_id": None,
            "prompt_match_count": 0,
            "mapping_status": "mapping_error",
            "dependency_closure_ready": False,
            "generation_case_ids": [],
            "missing_dependency_ids": [],
            "mapping_error": type(exc).__name__,
            "mapping_evidence_available": True,
        }
    dataset_loader_available = getattr(executable_builder, "load_dataset_entry", None) is not None or _map_record is not executable_builder._map_record
    return {
        "bfcl_case_id": mapped.get("bfcl_case_id"),
        "prompt_match_count": mapped.get("prompt_match_count"),
        "mapping_status": mapped.get("mapping_status") if dataset_loader_available else "bfcl_dataset_loader_unavailable",
        "dependency_closure_ready": bool(mapped.get("dependency_closure_ready")),
        "generation_case_ids": mapped.get("generation_case_ids") or [],
        "missing_dependency_ids": mapped.get("missing_dependency_ids") or [],
        "mapping_evidence_available": dataset_loader_available,
    }


def _classify_trace_candidate(item: dict[str, Any], source_root: Path, mapping_by_trace: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    audited = _audit_record(item, source_root, "control")
    mapping = _mapping_status(item, source_root, mapping_by_trace)
    no_explicit = _no_explicit_obligation(item)
    no_hidden = _no_hidden_state_dependency(item, no_explicit)
    baseline_no_activation = bool(audited.get("trace_exists") and audited.get("baseline_first_response_memory_call_count") == 0)
    if not mapping.get("mapping_evidence_available"):
        exact_mapping = None
    else:
        exact_mapping = bool(mapping.get("bfcl_case_id") and mapping.get("dependency_closure_ready") and mapping.get("mapping_status") in {"exact_current_user_prompt_match", "materialized_protocol_trace_index"})
    stage_status = {
        "no_explicit_obligation": _bool_status(no_explicit),
        "no_hidden_state_dependency": _bool_status(no_hidden),
        "baseline_no_memory_activation": _bool_status(baseline_no_activation),
        "exact_bfcl_mapping": _bool_status(exact_mapping),
    }
    reasons: list[str] = []
    for key, status in stage_status.items():
        if status != "pass":
            reasons.append(f"{key}_{status}")
    return {
        "audit_case_id": item.get("audit_case_id"),
        "source_audit_record_id": item.get("source_audit_record_id"),
        "candidate_id": item.get("candidate_id"),
        "memory_audit_source_key": item.get("memory_audit_source_key"),
        "category": item.get("category"),
        "trace_relative_path": item.get("trace_relative_path"),
        "bfcl_case_id": mapping.get("bfcl_case_id"),
        "mapping_status": mapping.get("mapping_status"),
        "prompt_match_count": mapping.get("prompt_match_count"),
        "dependency_closure_ready": mapping.get("dependency_closure_ready"),
        "mapping_evidence_available": mapping.get("mapping_evidence_available"),
        "missing_dependency_ids": mapping.get("missing_dependency_ids"),
        "generation_case_ids": mapping.get("generation_case_ids"),
        "operation": item.get("operation"),
        "operation_scope": item.get("operation_scope"),
        "rejection_reason": item.get("rejection_reason"),
        "review_rejection_reason": item.get("review_rejection_reason"),
        "memory_witness_strength": item.get("memory_witness_strength"),
        "baseline_first_response_function_call_count": audited.get("baseline_first_response_function_call_count"),
        "baseline_first_response_memory_call_count": audited.get("baseline_first_response_memory_call_count"),
        "baseline_first_response_memory_tools": audited.get("baseline_first_response_memory_tools"),
        "baseline_first_response_message_count": audited.get("baseline_first_response_message_count"),
        "trace_exists": audited.get("trace_exists"),
        "stage_status": stage_status,
        "clean_control_candidate": False,
        "clean_control_rejection_reasons": reasons,
    }


def _mark_uniqueness(records: list[dict[str, Any]], excluded_bfcl_case_ids: set[str]) -> None:
    bfcl_counts: dict[str, int] = {}
    trace_counts: dict[str, int] = {}
    audit_counts: dict[str, int] = {}
    for item in records:
        for value, counts in (
            (item.get("bfcl_case_id"), bfcl_counts),
            (item.get("trace_relative_path"), trace_counts),
            (item.get("audit_case_id"), audit_counts),
        ):
            if value:
                counts[str(value)] = counts.get(str(value), 0) + 1
    for item in records:
        bfcl = str(item.get("bfcl_case_id") or "")
        trace = str(item.get("trace_relative_path") or "")
        audit_id = str(item.get("audit_case_id") or "")
        if item.get("stage_status", {}).get("exact_bfcl_mapping") == "unknown":
            item["stage_status"]["uniqueness"] = "unknown"
            item["clean_control_rejection_reasons"].append("uniqueness_unknown_without_bfcl_mapping")
            item["clean_control_candidate"] = False
            continue
        uniqueness_pass = bool(
            bfcl
            and trace
            and audit_id
            and bfcl_counts.get(bfcl, 0) == 1
            and trace_counts.get(trace, 0) == 1
            and audit_counts.get(audit_id, 0) == 1
            and bfcl not in excluded_bfcl_case_ids
        )
        status = "pass" if uniqueness_pass else "fail"
        item["stage_status"]["uniqueness"] = status
        if not uniqueness_pass:
            if not bfcl or bfcl_counts.get(bfcl, 0) != 1:
                item["clean_control_rejection_reasons"].append("uniqueness_fail_bfcl_case_id")
            if not trace or trace_counts.get(trace, 0) != 1:
                item["clean_control_rejection_reasons"].append("uniqueness_fail_trace_relative_path")
            if not audit_id or audit_counts.get(audit_id, 0) != 1:
                item["clean_control_rejection_reasons"].append("uniqueness_fail_audit_case_id")
            if bfcl and bfcl in excluded_bfcl_case_ids:
                item["clean_control_rejection_reasons"].append("overlaps_selected_positive_bfcl_case_id")
        item["clean_control_candidate"] = all(value == "pass" for value in item["stage_status"].values())


def _reason_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in records:
        reasons = item.get("clean_control_rejection_reasons") or []
        if item.get("clean_control_candidate"):
            counts["clean_control_candidate"] = counts.get("clean_control_candidate", 0) + 1
        for reason in reasons:
            counts[str(reason)] = counts.get(str(reason), 0) + 1
    return dict(sorted(counts.items()))


def _stage_counts(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for item in records:
        for key, status in (item.get("stage_status") or {}).items():
            bucket = counts.setdefault(key, {"pass": 0, "fail": 0, "unknown": 0})
            bucket[str(status)] = bucket.get(str(status), 0) + 1
    return counts


def _duplicate_involved_count(records: list[dict[str, Any]], field: str) -> int:
    counts: dict[str, int] = {}
    for item in records:
        value = item.get(field)
        if value:
            key = str(value)
            counts[key] = counts.get(key, 0) + 1
    return sum(1 for item in records if item.get(field) and counts.get(str(item.get(field)), 0) > 1)


def _activation_count(records: list[dict[str, Any]]) -> int:
    return sum(1 for item in records if item.get("baseline_first_response_memory_call_count"))


def _source_negative_control_records(memory_audit: dict[str, Any], source_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _as_list(memory_audit.get("sample_rejections")):
        if not isinstance(item, dict):
            continue
        trace_relative = _trace_relative_from_audit(item)
        if not trace_relative:
            continue
        record = {
            "record_type": "control",
            "audit_case_id": item.get("candidate_id") or item.get("source_audit_record_id"),
            "source_audit_record_id": item.get("source_audit_record_id"),
            "category": item.get("category"),
            "trace_relative_path": trace_relative,
        }
        rows.append(_audit_record(record, source_root, "control"))
    return rows


def _materialized_control_record(item: dict[str, Any], source_root: Path) -> dict[str, Any]:
    audited = _audit_record(item, source_root, "control")
    no_explicit = _no_explicit_obligation(item)
    no_hidden = _no_hidden_state_dependency(item, no_explicit)
    baseline_no_activation = bool(audited.get("trace_exists") and audited.get("baseline_first_response_memory_call_count") == 0)
    exact_mapping = bool(item.get("bfcl_case_id") and item.get("prompt_match_count") == 1 and item.get("dependency_closure_ready"))
    clean = bool(no_explicit is True and no_hidden is True and baseline_no_activation and exact_mapping)
    reasons: list[str] = []
    if no_explicit is not True:
        reasons.append(f"no_explicit_obligation_{_bool_status(no_explicit)}")
    if no_hidden is not True:
        reasons.append(f"no_hidden_state_dependency_{_bool_status(no_hidden)}")
    if not baseline_no_activation:
        reasons.append("baseline_no_memory_activation_fail")
    if not exact_mapping:
        reasons.append("exact_bfcl_mapping_fail")
    return {
        "audit_case_id": item.get("audit_case_id"),
        "source_audit_record_id": item.get("source_audit_record_id"),
        "category": item.get("category"),
        "trace_relative_path": item.get("trace_relative_path"),
        "bfcl_case_id": item.get("bfcl_case_id"),
        "negative_control_type": item.get("negative_control_type"),
        "operation": item.get("operation"),
        "mapping_status": item.get("mapping_status"),
        "prompt_match_count": item.get("prompt_match_count"),
        "dependency_closure_ready": item.get("dependency_closure_ready"),
        "missing_dependency_ids": item.get("missing_dependency_ids") or [],
        "baseline_first_response_function_call_count": audited.get("baseline_first_response_function_call_count"),
        "baseline_first_response_memory_call_count": audited.get("baseline_first_response_memory_call_count"),
        "baseline_first_response_memory_tools": audited.get("baseline_first_response_memory_tools"),
        "stage_status": {
            "no_explicit_obligation": _bool_status(no_explicit),
            "no_hidden_state_dependency": _bool_status(no_hidden),
            "baseline_no_memory_activation": _bool_status(baseline_no_activation),
            "exact_bfcl_mapping": _bool_status(exact_mapping),
        },
        "true_control_candidate": clean,
        "true_control_rejection_reasons": reasons,
    }


def evaluate(
    protocol_path: Path = DEFAULT_PROTOCOL,
    memory_audit_path: Path = DEFAULT_MEMORY_AUDIT,
    source_root: Path = DEFAULT_SOURCE_ROOT,
    categories: tuple[str, ...] = DEFAULT_CATEGORIES,
) -> dict[str, Any]:
    protocol = _load_json(protocol_path)
    memory_audit = _load_json(memory_audit_path)
    protocol = protocol if isinstance(protocol, dict) else {}
    memory_audit = memory_audit if isinstance(memory_audit, dict) else {}
    selected_positive_rows = _rows_from_protocol(protocol, "selected_positive_cases")
    selected_control_rows = _rows_from_protocol(protocol, "selected_control_cases")
    protocol_control_rows = _rows_from_protocol(protocol, "selected_control_cases", "control_selection_rejections")
    selected_controls = [_materialized_control_record(item, source_root) for item in selected_control_rows]
    materialized_controls = [_materialized_control_record(item, source_root) for item in protocol_control_rows]
    true_materialized_controls = [item for item in materialized_controls if item.get("true_control_candidate")]

    audit_by_trace = _audit_index_by_trace(memory_audit)
    trace_records = _memory_capable_trace_records(source_root, categories, audit_by_trace)
    mapping_by_trace = _protocol_mapping_by_trace(protocol)
    classified_trace_records = [_classify_trace_candidate(item, source_root, mapping_by_trace) for item in trace_records]
    no_activation_records = [item for item in classified_trace_records if item["stage_status"].get("baseline_no_memory_activation") == "pass"]
    selected_positive_bfcl_ids = {str(item.get("bfcl_case_id")) for item in selected_positive_rows if item.get("bfcl_case_id")}
    _mark_uniqueness(no_activation_records, selected_positive_bfcl_ids)
    clean_source_candidates = [item for item in no_activation_records if item.get("clean_control_candidate")]

    category_counts: dict[str, int] = {}
    no_activation_category_counts: dict[str, int] = {}
    for item in classified_trace_records:
        category = str(item.get("category") or "unknown")
        category_counts[category] = category_counts.get(category, 0) + 1
    for item in no_activation_records:
        category = str(item.get("category") or "unknown")
        no_activation_category_counts[category] = no_activation_category_counts.get(category, 0) + 1

    required_true_control_count = int(protocol.get("control_target_count") or 8)
    source_negative_controls = _source_negative_control_records(memory_audit, source_root)
    source_pool_negative_control_activation_count = _activation_count(source_negative_controls)
    materialized_protocol_negative_control_activation_count = _activation_count(materialized_controls)
    materialized_selected_control_activation_count = _activation_count(selected_controls)
    selected_smoke_baseline_control_activation_count = 0
    clean_selected_control_count = sum(1 for item in selected_controls if item.get("true_control_candidate"))
    unknown_mapping_count = sum(1 for item in no_activation_records if item.get("stage_status", {}).get("exact_bfcl_mapping") == "unknown")
    ambiguous_bfcl_mapping_count = sum(1 for item in no_activation_records if "ambiguous" in str(item.get("mapping_status") or ""))
    dependency_missing_count = sum(1 for item in no_activation_records + materialized_controls if item.get("missing_dependency_ids"))
    positive_control_overlap_count = sum(1 for item in no_activation_records if item.get("bfcl_case_id") and str(item.get("bfcl_case_id")) in selected_positive_bfcl_ids)
    duplicate_bfcl_case_id_count = _duplicate_involved_count(no_activation_records, "bfcl_case_id")
    duplicate_trace_relative_path_count = _duplicate_involved_count(no_activation_records, "trace_relative_path")
    duplicate_audit_case_id_count = _duplicate_involved_count(no_activation_records, "audit_case_id")
    selected_duplicate_bfcl_case_id_count = _duplicate_involved_count(selected_controls, "bfcl_case_id")
    selected_duplicate_trace_relative_path_count = _duplicate_involved_count(selected_controls, "trace_relative_path")
    selected_duplicate_audit_case_id_count = _duplicate_involved_count(selected_controls, "audit_case_id")

    blockers: list[str] = []
    if len(true_materialized_controls) < required_true_control_count:
        blockers.append("materialized_protocol_true_controls_below_target")
    if not clean_source_candidates:
        blockers.append("no_clean_source_controls_found")
    if unknown_mapping_count:
        blockers.append("source_candidates_have_unknown_required_fields")

    clean_control_source_audit_ready = bool(protocol and memory_audit and classified_trace_records)

    return {
        "report_scope": "explicit_obligation_clean_control_source_audit",
        "clean_control_source_audit_ready": clean_control_source_audit_ready,
        "artifact_kind": "clean_control_insufficiency_audit",
        "diagnostic_only": True,
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "scorer_or_model_run": False,
        "controlled_smoke_approved": False,
        "scorer_authorization_ready": False,
        "bfcl_performance_claim_allowed": False,
        "sota_3pp_claim_allowed": False,
        "execution_allowed": False,
        "smoke_ready": False,
        "smoke_selection_ready_after_baseline_dry_audit": False,
        "selection_gate_passed": False,
        "claim_boundary_acknowledged": True,
        "polluted_controls_not_counted_as_clean": True,
        "materialized_controls_reported_separately": True,
        "unknown_mapping_is_blocker": bool(unknown_mapping_count),
        "ambiguous_mapping_is_blocker": bool(ambiguous_bfcl_mapping_count),
        "candidate_commands": [],
        "planned_commands": [],
        "materialized_protocol_control_count": len(materialized_controls),
        "materialized_selected_control_count": len(selected_controls),
        "selected_smoke_control_count": 0,
        "true_control_available_count": len(true_materialized_controls),
        "required_true_control_count": required_true_control_count,
        "clean_selected_control_count": clean_selected_control_count,
        "materialized_selected_control_activation_count": materialized_selected_control_activation_count,
        "materialized_selected_control_baseline_activation_count": materialized_selected_control_activation_count,
        "selected_smoke_baseline_control_activation_count": selected_smoke_baseline_control_activation_count,
        "source_pool_negative_control_activation_count": source_pool_negative_control_activation_count,
        "materialized_protocol_negative_control_activation_count": materialized_protocol_negative_control_activation_count,
        "duplicate_bfcl_case_id_count": duplicate_bfcl_case_id_count,
        "duplicate_trace_relative_path_count": duplicate_trace_relative_path_count,
        "duplicate_audit_case_id_count": duplicate_audit_case_id_count,
        "selected_duplicate_bfcl_case_id_count": selected_duplicate_bfcl_case_id_count,
        "selected_duplicate_trace_relative_path_count": selected_duplicate_trace_relative_path_count,
        "selected_duplicate_audit_case_id_count": selected_duplicate_audit_case_id_count,
        "positive_control_overlap_count": positive_control_overlap_count,
        "ambiguous_bfcl_mapping_count": ambiguous_bfcl_mapping_count,
        "dependency_missing_count": dependency_missing_count,
        "unknown_mapping_count": unknown_mapping_count,
        "clean_source_control_candidate_count": len(clean_source_candidates),
        "inputs": {
            "protocol_path": str(protocol_path),
            "memory_audit_path": str(memory_audit_path),
            "source_root": str(source_root),
            "categories": list(categories),
        },
        "summary": {
            "materialized_protocol_control_count": len(materialized_controls),
            "materialized_selected_control_count": len(selected_controls),
            "materialized_protocol_true_control_count": len(true_materialized_controls),
            "clean_selected_control_count": clean_selected_control_count,
            "materialized_protocol_negative_control_activation_count": materialized_protocol_negative_control_activation_count,
            "materialized_selected_control_activation_count": materialized_selected_control_activation_count,
        "materialized_selected_control_baseline_activation_count": materialized_selected_control_activation_count,
            "source_pool_negative_control_activation_count": source_pool_negative_control_activation_count,
            "selected_smoke_baseline_control_activation_count": selected_smoke_baseline_control_activation_count,
            "source_trace_count": len(classified_trace_records),
            "source_trace_count_by_category": dict(sorted(category_counts.items())),
            "memory_capable_no_activation_trace_count": len(no_activation_records),
            "memory_capable_no_activation_trace_count_by_category": dict(sorted(no_activation_category_counts.items())),
            "clean_source_control_candidate_count": len(clean_source_candidates),
            "no_activation_stage_counts": _stage_counts(no_activation_records),
            "no_activation_rejection_reason_counts": _reason_counts(no_activation_records),
        },
        "materialized_control_stage_counts": _stage_counts(materialized_controls),
        "materialized_controls": materialized_controls,
        "source_no_activation_candidates": no_activation_records,
        "recommended_clean_control_candidates": clean_source_candidates,
        "blockers": blockers,
        "next_required_action": "materialize_clean_source_controls_to_bfcl_executable_protocol_before_smoke" if clean_source_candidates else "transition_to_evidence_grounding_prior_offline_audit",
        "next_required_actions": (["materialize_clean_source_controls_to_bfcl_executable_protocol_before_smoke", "rerun_baseline_dry_audit_on_materialized_clean_controls", "rerun_smoke_ready_checker"] if clean_source_candidates else ["transition_to_evidence_grounding_prior_offline_audit"]),
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    top_reasons = summary.get("no_activation_rejection_reason_counts") or {}
    reason_lines = [f"- `{key}`: `{value}`" for key, value in list(top_reasons.items())[:12]]
    candidates = report.get("recommended_clean_control_candidates") or []
    candidate_lines = [
        f"- `{item.get('bfcl_case_id')}` `{item.get('category')}` `{item.get('trace_relative_path')}`"
        for item in candidates[:10]
    ]
    return "\n".join([
        "# Explicit Obligation Clean-Control Source Audit",
        "",
        f"- Artifact kind: `{report['artifact_kind']}`",
        f"- Diagnostic only: `{report['diagnostic_only']}`",
        f"- Offline only: `{report['offline_only']}`",
        f"- Execution allowed: `{report['execution_allowed']}`",
        f"- Smoke ready: `{report['smoke_ready']}`",
        f"- Selection gate passed: `{report['selection_gate_passed']}`",
        f"- Scorer or model run: `{report['scorer_or_model_run']}`",
        f"- Polluted controls counted as clean: `{not report['polluted_controls_not_counted_as_clean']}`",
        f"- Clean-control source audit ready: `{report['clean_control_source_audit_ready']}`",
        f"- Materialized protocol controls / selected controls / true controls: `{report['materialized_protocol_control_count']}` / `{report['materialized_selected_control_count']}` / `{report['true_control_available_count']}`",
        f"- Clean selected controls: `{report['clean_selected_control_count']}` / `{report['required_true_control_count']}`",
        f"- Materialized protocol negative-control activations: `{summary['materialized_protocol_negative_control_activation_count']}`",
        f"- Source traces scanned: `{summary['source_trace_count']}`",
        f"- Memory-capable no-activation traces: `{summary['memory_capable_no_activation_trace_count']}`",
        f"- Clean source control candidates: `{summary['clean_source_control_candidate_count']}`",
        f"- Source trace counts by category: `{summary['source_trace_count_by_category']}`",
        f"- No-activation stage counts: `{summary['no_activation_stage_counts']}`",
        f"- Source/materialized/materialized-selected activation counts: `{report['source_pool_negative_control_activation_count']}` / `{report['materialized_protocol_negative_control_activation_count']}` / `{report['materialized_selected_control_activation_count']}`",
        f"- Duplicate BFCL/trace/audit counts: `{report['duplicate_bfcl_case_id_count']}` / `{report['duplicate_trace_relative_path_count']}` / `{report['duplicate_audit_case_id_count']}`",
        f"- Overlap / ambiguous / dependency-missing counts: `{report['positive_control_overlap_count']}` / `{report['ambiguous_bfcl_mapping_count']}` / `{report['dependency_missing_count']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "## Dominant No-Activation Rejection Reasons",
        "",
        *(reason_lines or ["- `none`: `0`"]),
        "",
        "## Recommended Clean-Control Candidates",
        "",
        *(candidate_lines or ["- None found under fail-closed criteria."]),
        "",
        "This diagnostic reads existing artifacts only. It does not run BFCL, model inference, or scorer execution.",
        "",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--memory-audit", type=Path, default=DEFAULT_MEMORY_AUDIT)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args(argv)
    categories = tuple(args.categories) if args.categories else DEFAULT_CATEGORIES
    report = evaluate(args.protocol, args.memory_audit, args.source_root, categories)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        compact_keys = [
            "clean_control_source_audit_ready",
            "artifact_kind",
            "diagnostic_only",
            "offline_only",
            "does_not_call_bfcl_or_model",
            "does_not_authorize_scorer",
            "scorer_or_model_run",
            "controlled_smoke_approved",
            "scorer_authorization_ready",
            "bfcl_performance_claim_allowed",
            "sota_3pp_claim_allowed",
            "execution_allowed",
            "smoke_ready",
            "smoke_selection_ready_after_baseline_dry_audit",
            "selection_gate_passed",
            "claim_boundary_acknowledged",
            "polluted_controls_not_counted_as_clean",
            "materialized_controls_reported_separately",
            "unknown_mapping_is_blocker",
            "ambiguous_mapping_is_blocker",
            "materialized_protocol_control_count",
            "materialized_selected_control_count",
            "selected_smoke_control_count",
            "true_control_available_count",
            "required_true_control_count",
            "clean_selected_control_count",
            "source_pool_negative_control_activation_count",
            "materialized_protocol_negative_control_activation_count",
            "materialized_selected_control_activation_count",
            "materialized_selected_control_baseline_activation_count",
            "selected_smoke_baseline_control_activation_count",
            "duplicate_bfcl_case_id_count",
            "duplicate_trace_relative_path_count",
            "duplicate_audit_case_id_count",
            "selected_duplicate_bfcl_case_id_count",
            "selected_duplicate_trace_relative_path_count",
            "selected_duplicate_audit_case_id_count",
            "positive_control_overlap_count",
            "ambiguous_bfcl_mapping_count",
            "dependency_missing_count",
            "unknown_mapping_count",
            "clean_source_control_candidate_count",
            "candidate_commands",
            "planned_commands",
            "blockers",
            "next_required_action",
        ]
        compact = {key: report.get(key) for key in compact_keys}
        compact["summary"] = report.get("summary")
        print(json.dumps(compact, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
