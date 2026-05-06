#!/usr/bin/env python3
"""Check the RASHE behavior evolution archive artifacts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ARTIFACT_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_ARCHIVE = ARTIFACT_ROOT / "rashe_evolution_archive" / "archive_index.json"
REQUIRED_ENTRY_FIELDS = {
    "artifact_kind",
    "schema_version",
    "entry_id",
    "entry_type",
    "evolution_subject",
    "status",
    "dev_score_status",
    "target_behavior_cluster",
    "not_bfcl_category_bound",
    "source_evidence",
    "forbidden_inputs",
    "feedback_slots",
    "boundary_flags",
    "next_allowed_transition",
}
REQUIRED_SOURCE_FIELDS = {"source_diagnostics_commit", "primary_bucket_total", "category_coverage", "compact_bucket_counts", "evidence_kind"}
REQUIRED_FEEDBACK_SLOTS = {
    "dev_accuracy_delta_pp",
    "fixed_count",
    "regressed_count",
    "target_bucket_reduction",
    "cost_delta_pct",
    "latency_delta_pct",
    "leakage_count",
}
REQUIRED_INDEX_FALSE_KEYS = {
    "performance_evidence",
    "scorer_authorized",
    "candidate_pool_ready",
    "candidate_jsonl_authorized",
    "candidate_activation_authorized",
    "provider_calls_authorized",
    "bfcl_generate_authorized",
    "bfcl_evaluate_authorized",
    "huawei_acceptance_ready",
    "sota_3pp_claim_ready",
}
REQUIRED_BOUNDARY_FALSE_KEYS = REQUIRED_INDEX_FALSE_KEYS
ALLOWED_ENTRY_TYPES = {"skill_metadata_candidate", "router_policy_candidate", "verifier_candidate", "workflow_candidate", "proposal_policy_candidate", "watchlist_cluster"}
ALLOWED_EVOLUTION_SUBJECTS = {"skill_metadata", "router_policy", "verifier_stop_condition", "workflow_patch", "proposal_policy"}
ALLOWED_STATUSES = {"seed_archive_entry", "proposal_ready", "dev_smoke_requested", "dev_smoke_authorized", "dev_smoke_executed", "dev_passed", "demoted", "rejected", "holdout_requested", "holdout_authorized", "holdout_passed", "watch"}
ALLOWED_FORBIDDEN_INPUT_VALUES = {
    "gold",
    "expected",
    "reference",
    "scorer_diff",
    "candidate_output",
    "raw_trace",
    "raw_case_id",
    "raw_prompt",
    "raw_payload",
    "provider_exchange",
    "tool_argument_values",
}
SINGLE_SUBSET_RE = re.compile(r"(multi_turn_miss_param|multi_turn_miss_func|multi_turn_long_context|multi_turn_base|agentic_web_search|agentic_memory|live_simple|live_multiple|non_live_simple|non_live_multiple).*(?:skill|candidate)|(?:skill|candidate).*(multi_turn_miss_param|multi_turn_miss_func|multi_turn_long_context|multi_turn_base|agentic_web_search|agentic_memory|live_simple|live_multiple|non_live_simple|non_live_multiple)", re.I)
FORBIDDEN_KEY_RE = re.compile(r"(^|_)(raw_(?:prompt|trace|payload|provider|request|response|header|body|case_id)|prompt_text|trace_text|provider_exchange|case_id|gold|expected|reference|tool_args?|tool_arguments?|scorer_diff|candidate_output)(_|$)", re.I)
FORBIDDEN_VALUE_RE = re.compile(r"sk-[A-Za-z0-9_-]{16,}|bearer |api key|secret|raw prompt|raw trace|raw payload|provider exchange|case id|gold answer|expected answer|reference answer|tool argument values|scorer diff|candidate output text|huawei readiness|\+3pp ready", re.I)


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _walk(value: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    items = [(path, value)]
    if isinstance(value, dict):
        for key, child in value.items():
            items.extend(_walk(child, path + (str(key),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            items.extend(_walk(child, path + (str(index),)))
    return items


def _is_allowed_forbidden_input(path: tuple[str, ...], value: Any) -> bool:
    return len(path) >= 2 and path[-2] == "forbidden_inputs" and value in ALLOWED_FORBIDDEN_INPUT_VALUES


def _scan_forbidden_material(data: dict[str, Any], *, prefix: str) -> list[str]:
    blockers: list[str] = []
    allowed_keys = {
        "forbidden_inputs",
        "source_case_count",
        "primary_bucket_total",
        "category_coverage_count",
        "candidate_pool_ready",
        "candidate_jsonl_authorized",
        "candidate_activation_authorized",
        "candidate_interpretation",
        "candidate_pool_created",
        "candidate_jsonl_created",
        "raw_outputs_committed",
    }
    for path, value in _walk(data):
        key = path[-1] if path else ""
        dotted = ".".join(path)
        if key and key not in allowed_keys and FORBIDDEN_KEY_RE.search(key):
            blockers.append(f"{prefix}_forbidden_key:{dotted}")
        if isinstance(value, str) and FORBIDDEN_VALUE_RE.search(value):
            if _is_allowed_forbidden_input(path, value):
                continue
            blockers.append(f"{prefix}_forbidden_value:{dotted}")
    return sorted(set(blockers))


def _validate_false_keys(data: dict[str, Any], keys: set[str], *, prefix: str) -> list[str]:
    blockers: list[str] = []
    for key in sorted(keys):
        if data.get(key) is not False:
            blockers.append(f"{prefix}_{key}_not_false:{data.get(key)!r}")
    return blockers


def _validate_entry(entry: dict[str, Any], index_item: dict[str, Any] | None = None) -> list[str]:
    blockers: list[str] = []
    missing = sorted(REQUIRED_ENTRY_FIELDS - set(entry))
    if missing:
        blockers.append(f"entry_required_fields_missing:{entry.get('entry_id', '<unknown>')}:{missing}")
        return blockers
    entry_id = str(entry.get("entry_id"))
    if entry.get("artifact_kind") != "rashe_evolution_archive_entry":
        blockers.append(f"entry_{entry_id}_artifact_kind_invalid:{entry.get('artifact_kind')!r}")
    if entry.get("schema_version") != "rashe_archive_v0":
        blockers.append(f"entry_{entry_id}_schema_version_invalid:{entry.get('schema_version')!r}")
    if entry.get("entry_type") not in ALLOWED_ENTRY_TYPES:
        blockers.append(f"entry_{entry_id}_entry_type_invalid:{entry.get('entry_type')!r}")
    if entry.get("evolution_subject") not in ALLOWED_EVOLUTION_SUBJECTS:
        blockers.append(f"entry_{entry_id}_evolution_subject_invalid:{entry.get('evolution_subject')!r}")
    if entry.get("status") not in ALLOWED_STATUSES:
        blockers.append(f"entry_{entry_id}_status_invalid:{entry.get('status')!r}")
    if entry.get("not_bfcl_category_bound") is not True:
        blockers.append(f"entry_{entry_id}_not_bfcl_category_bound_not_true")
    for field in ("entry_id", "target_behavior_cluster"):
        if SINGLE_SUBSET_RE.search(str(entry.get(field, ""))):
            blockers.append(f"entry_{entry_id}_category_bound_name:{field}:{entry.get(field)!r}")
    source = entry.get("source_evidence") if isinstance(entry.get("source_evidence"), dict) else {}
    missing_source = sorted(REQUIRED_SOURCE_FIELDS - set(source))
    if missing_source:
        blockers.append(f"entry_{entry_id}_source_evidence_missing:{missing_source}")
    if not isinstance(source.get("category_coverage"), list) or not source.get("category_coverage"):
        blockers.append(f"entry_{entry_id}_category_coverage_empty")
    if not isinstance(source.get("primary_bucket_total"), int) or source.get("primary_bucket_total") <= 0:
        blockers.append(f"entry_{entry_id}_primary_bucket_total_invalid:{source.get('primary_bucket_total')!r}")
    if set(entry.get("feedback_slots") or {}) != REQUIRED_FEEDBACK_SLOTS:
        blockers.append(f"entry_{entry_id}_feedback_slots_invalid:{sorted((entry.get('feedback_slots') or {}).keys())}")
    if entry.get("dev_score_status") != "not_run":
        blockers.append(f"entry_{entry_id}_dev_score_status_not_not_run:{entry.get('dev_score_status')!r}")
    forbidden_inputs = set(entry.get("forbidden_inputs") or [])
    if not ALLOWED_FORBIDDEN_INPUT_VALUES.issubset(forbidden_inputs):
        blockers.append(f"entry_{entry_id}_forbidden_inputs_missing:{sorted(ALLOWED_FORBIDDEN_INPUT_VALUES - forbidden_inputs)}")
    boundary = entry.get("boundary_flags") if isinstance(entry.get("boundary_flags"), dict) else {}
    blockers.extend(_validate_false_keys(boundary, REQUIRED_BOUNDARY_FALSE_KEYS, prefix=f"entry_{entry_id}_boundary"))
    if index_item is not None:
        if index_item.get("entry_id") != entry_id:
            blockers.append(f"entry_{entry_id}_index_entry_id_mismatch:{index_item.get('entry_id')!r}")
        if index_item.get("entry_type") != entry.get("entry_type"):
            blockers.append(f"entry_{entry_id}_index_entry_type_mismatch")
        if index_item.get("status") != entry.get("status"):
            blockers.append(f"entry_{entry_id}_index_status_mismatch")
        if index_item.get("target_behavior_cluster") != entry.get("target_behavior_cluster"):
            blockers.append(f"entry_{entry_id}_index_target_behavior_cluster_mismatch")
        if index_item.get("source_case_count") != source.get("primary_bucket_total"):
            blockers.append(f"entry_{entry_id}_index_source_case_count_mismatch")
        if index_item.get("category_coverage_count") != len(source.get("category_coverage") or []):
            blockers.append(f"entry_{entry_id}_index_category_coverage_count_mismatch")
        if index_item.get("dev_score_status") != entry.get("dev_score_status"):
            blockers.append(f"entry_{entry_id}_index_dev_score_status_mismatch")
    blockers.extend(_scan_forbidden_material(entry, prefix=f"entry_{entry_id}"))
    return sorted(set(blockers))


def validate_archive(index: dict[str, Any], *, base_path: Path | None = None) -> list[str]:
    blockers: list[str] = []
    if index.get("artifact_kind") != "rashe_evolution_archive_index":
        blockers.append(f"index_artifact_kind_invalid:{index.get('artifact_kind')!r}")
    if index.get("schema_version") != "rashe_archive_v0":
        blockers.append(f"index_schema_version_invalid:{index.get('schema_version')!r}")
    if index.get("archive_scope") != "behavior_level_candidate_archive_not_bfcl_category_skill_mapping":
        blockers.append(f"index_archive_scope_invalid:{index.get('archive_scope')!r}")
    if index.get("not_bfcl_category_bound") is not True:
        blockers.append("index_not_bfcl_category_bound_not_true")
    if index.get("rejected_and_demoted_entries_retained") is not True:
        blockers.append("index_rejected_and_demoted_entries_retained_not_true")
    blockers.extend(_validate_false_keys(index, REQUIRED_INDEX_FALSE_KEYS, prefix="index"))
    entries = index.get("entries")
    if not isinstance(entries, list) or not entries:
        blockers.append("index_entries_missing_or_empty")
        return sorted(set(blockers))
    seen: set[str] = set()
    root = Path(".") if base_path is None else base_path
    for item in entries:
        if not isinstance(item, dict):
            blockers.append(f"index_entry_not_object:{item!r}")
            continue
        entry_id = item.get("entry_id")
        if not isinstance(entry_id, str) or not entry_id:
            blockers.append(f"index_entry_id_invalid:{entry_id!r}")
            continue
        if entry_id in seen:
            blockers.append(f"index_duplicate_entry_id:{entry_id}")
        seen.add(entry_id)
        if SINGLE_SUBSET_RE.search(entry_id):
            blockers.append(f"index_category_bound_entry_id:{entry_id}")
        path_value = item.get("entry_path")
        if not isinstance(path_value, str):
            blockers.append(f"index_entry_path_invalid:{entry_id}:{path_value!r}")
            continue
        entry_path = root / path_value
        if not entry_path.exists():
            blockers.append(f"index_entry_path_missing:{entry_id}:{path_value}")
            continue
        try:
            entry = _load(entry_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            blockers.append(f"index_entry_load_failed:{entry_id}:{exc}")
            continue
        blockers.extend(_validate_entry(entry, item))
    blockers.extend(_scan_forbidden_material(index, prefix="index"))
    return sorted(set(blockers))


def check(path: Path = DEFAULT_ARCHIVE) -> dict[str, Any]:
    index = _load(path)
    blockers = validate_archive(index, base_path=Path("."))
    return {
        "report_scope": "rashe_evolution_archive_check",
        "archive_index": str(path),
        "schema_version": index.get("schema_version"),
        "archive_status": index.get("archive_status"),
        "entry_count": len(index.get("entries", [])) if isinstance(index.get("entries"), list) else 0,
        "proposal_ready_entry_count": sum(1 for item in index.get("entries", []) if isinstance(item, dict) and item.get("status") == "proposal_ready") if isinstance(index.get("entries"), list) else 0,
        "performance_evidence": index.get("performance_evidence"),
        "scorer_authorized": index.get("scorer_authorized"),
        "candidate_pool_ready": index.get("candidate_pool_ready"),
        "rashe_evolution_archive_passed": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-index", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    try:
        summary = check(args.archive_index)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        summary = {
            "report_scope": "rashe_evolution_archive_check",
            "archive_index": str(args.archive_index),
            "rashe_evolution_archive_passed": False,
            "blockers": [f"load_failed:{exc}"],
        }
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_evolution_archive_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
