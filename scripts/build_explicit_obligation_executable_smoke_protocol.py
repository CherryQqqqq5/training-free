#!/usr/bin/env python3
"""Materialize explicit-obligation audit candidates into BFCL case ids.

This is an offline builder. It maps source traces to BFCL dataset case ids using
strict exact current-user prompt matching, expands dependency closure, and writes
a review manifest. It does not emit scorer commands or authorize execution.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

try:  # Imported at module scope so tests can monkeypatch it.
    from bfcl_eval.utils import load_dataset_entry
except Exception:  # pragma: no cover - minimal test env
    load_dataset_entry = None  # type: ignore[assignment]

DEFAULT_MEMORY_AUDIT = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_obligation_audit.json")
DEFAULT_SOURCE_ROOT = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
DEFAULT_OUT = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_executable_smoke_protocol.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_executable_smoke_protocol.md")
PROVIDER = "novacode"


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _norm(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


@lru_cache(maxsize=None)
def _entries_by_id(category: str) -> dict[str, dict[str, Any]]:
    if load_dataset_entry is None:
        return {}
    try:
        entries = load_dataset_entry(category, include_prereq=True)  # type: ignore[misc]
    except TypeError:
        entries = load_dataset_entry(category)  # type: ignore[misc]
    except Exception:
        return {}
    return {str(entry.get("id")): entry for entry in entries if isinstance(entry, dict) and entry.get("id")}


@lru_cache(maxsize=None)
def _prompt_index(category: str) -> dict[str, list[str]]:
    index: dict[str, list[str]] = {}

    def walk(obj: Any, entry_id: str) -> None:
        if isinstance(obj, dict):
            if obj.get("role") == "user" and isinstance(obj.get("content"), str):
                index.setdefault(_norm(obj["content"]), []).append(entry_id)
            for value in obj.values():
                walk(value, entry_id)
        elif isinstance(obj, list):
            for value in obj:
                walk(value, entry_id)

    for entry_id, entry in _entries_by_id(category).items():
        walk(entry.get("question"), entry_id)
    return index


def _current_user_prompt(trace_path: Path) -> str | None:
    trace = _load_json(trace_path)
    if not isinstance(trace, dict):
        return None
    request_original = trace.get("request_original") or {}
    messages = request_original.get("input") or request_original.get("messages") or []
    if not isinstance(messages, list):
        return None
    users = [item.get("content") for item in messages if isinstance(item, dict) and item.get("role") == "user" and isinstance(item.get("content"), str)]
    return users[-1] if users else None


def _expand_deps(case_id: str, entries_by_id: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    expanded: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    def add(item_id: str) -> None:
        if item_id in seen:
            return
        seen.add(item_id)
        entry = entries_by_id.get(item_id)
        if entry is None:
            missing.append(item_id)
            return
        for dep_id in entry.get("depends_on") or []:
            add(str(dep_id))
        expanded.append(item_id)

    add(case_id)
    return expanded, sorted(set(missing))


def _map_record(item: dict[str, Any], source_root: Path, record_type: str) -> dict[str, Any]:
    category = str(item.get("category") or "")
    trace_relative = str(item.get("trace_relative_path") or item.get("source_audit_record_pointer_debug_only") or "")
    trace_path = source_root / trace_relative if trace_relative else None
    prompt = _current_user_prompt(trace_path) if trace_path else None
    prompt_norm = _norm(prompt)
    matches = _prompt_index(category).get(prompt_norm, []) if category and prompt_norm else []
    unique = len(matches) == 1
    bfcl_case_id = matches[0] if unique else None
    entries = _entries_by_id(category) if category else {}
    generation_ids: list[str] = []
    missing_deps: list[str] = []
    if bfcl_case_id:
        generation_ids, missing_deps = _expand_deps(bfcl_case_id, entries)
    mapping_status = "exact_current_user_prompt_match" if unique else ("ambiguous_current_user_prompt_match" if matches else "no_current_user_prompt_match")
    ready = bool(bfcl_case_id and entries and not missing_deps)
    return {
        "record_type": record_type,
        "audit_case_id": item.get("candidate_id") or item.get("source_audit_record_id"),
        "source_audit_record_id": item.get("source_audit_record_id"),
        "category": category,
        "trace_relative_path": trace_relative,
        "trace_exists": bool(trace_path and trace_path.exists()),
        "current_user_prompt": prompt,
        "bfcl_case_id": bfcl_case_id,
        "bfcl_case_id_mapping_method": "exact_current_user_prompt_match" if unique else None,
        "prompt_match_count": len(matches),
        "prompt_match_case_ids": matches,
        "mapping_status": mapping_status,
        "dependency_closure_ready": ready,
        "generation_case_ids": generation_ids,
        "missing_dependency_ids": missing_deps,
        "operation": item.get("operation"),
        "operation_cue": item.get("operation_cue"),
        "negative_control_type": item.get("rejection_reason") or item.get("review_rejection_reason"),
        "risk_level": item.get("risk_level"),
        "recommended_tools": item.get("recommended_tools") or [],
        "exact_tool_choice": False,
        "argument_creation": False,
        "expected_policy": "soft_guidance_only_memory_retrieve" if record_type == "positive" else "no_activation_expected",
    }


def _positive_source_records(memory_audit: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in memory_audit.get("candidate_records") or []:
        if not isinstance(item, dict):
            continue
        if item.get("candidate_ready") is True and item.get("risk_level") == "low" and item.get("operation") == "retrieve":
            rows.append(item)
    return rows


def _control_source_records(memory_audit: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in memory_audit.get("sample_rejections") or [] if isinstance(item, dict)]


def _select_unique(mapped: list[dict[str, Any]], limit: int, excluded_case_ids: set[str] | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    excluded = set(excluded_case_ids or set())
    selected: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in mapped:
        case_id = item.get("bfcl_case_id")
        if not item.get("dependency_closure_ready"):
            rejected.append({**item, "selection_rejection_reason": "not_mapped_or_dependency_not_ready"})
            continue
        if case_id in excluded:
            rejected.append({**item, "selection_rejection_reason": "overlaps_excluded_case_id"})
            continue
        if case_id in seen:
            rejected.append({**item, "selection_rejection_reason": "duplicate_bfcl_case_id"})
            continue
        if len(selected) >= limit:
            rejected.append({**item, "selection_rejection_reason": "selection_limit_reached"})
            continue
        seen.add(str(case_id))
        selected.append(item)
    return selected, rejected


def _hash_payload(payload: Any) -> str:
    stable = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(stable).hexdigest()


def evaluate(memory_audit_path: Path = DEFAULT_MEMORY_AUDIT, source_root: Path = DEFAULT_SOURCE_ROOT, positive_limit: int = 12, control_limit: int = 8) -> dict[str, Any]:
    _entries_by_id.cache_clear()
    _prompt_index.cache_clear()
    memory_audit = _load_json(memory_audit_path)
    memory_audit = memory_audit if isinstance(memory_audit, dict) else {}
    mapped_positive = [_map_record(item, source_root, "positive") for item in _positive_source_records(memory_audit)]
    positives, positive_rejections = _select_unique(mapped_positive, positive_limit)
    positive_case_ids = {str(item["bfcl_case_id"]) for item in positives if item.get("bfcl_case_id")}
    mapped_controls = [_map_record(item, source_root, "control") for item in _control_source_records(memory_audit)]
    controls, control_rejections = _select_unique(mapped_controls, control_limit, excluded_case_ids=positive_case_ids)
    selected = positives + controls
    target_ids_by_category: dict[str, list[str]] = {}
    generation_ids_by_category: dict[str, list[str]] = {}
    for item in selected:
        category = str(item.get("category") or "")
        target_ids_by_category.setdefault(category, []).append(str(item.get("bfcl_case_id")))
        for generation_id in item.get("generation_case_ids") or []:
            if generation_id not in generation_ids_by_category.setdefault(category, []):
                generation_ids_by_category[category].append(str(generation_id))
    ready = len(positives) == positive_limit and len(controls) == control_limit
    blockers: list[str] = []
    if len(positives) < positive_limit:
        blockers.append("positive_executable_cases_below_target")
    if len(controls) < control_limit:
        blockers.append("control_executable_cases_below_target")
    if not selected:
        blockers.append("no_executable_cases_selected")
    return {
        "report_scope": "explicit_obligation_executable_smoke_protocol",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "bfcl_executable_manifest_ready": ready,
        "protocol_ready_for_review": ready,
        "approval_status": "pending",
        "execution_allowed": False,
        "separate_approval_required_before_execution": True,
        "allowed_provider_profiles": [PROVIDER],
        "future_provider_profile": PROVIDER,
        "future_model_route": "gpt-5.4",
        "selection_method": "exact_current_user_prompt_match_unique_and_disjoint",
        "positive_target_count": positive_limit,
        "control_target_count": control_limit,
        "positive_case_count": len(positives),
        "control_case_count": len(controls),
        "selected_case_count": len(selected),
        "mapped_positive_candidate_count": sum(1 for item in mapped_positive if item.get("dependency_closure_ready")),
        "mapped_control_candidate_count": sum(1 for item in mapped_controls if item.get("dependency_closure_ready")),
        "selected_positive_cases": positives,
        "selected_control_cases": controls,
        "positive_selection_rejections": positive_rejections,
        "control_selection_rejections": control_rejections,
        "target_ids_by_category": target_ids_by_category,
        "generation_ids_by_category": generation_ids_by_category,
        "selected_case_list_hash": _hash_payload(selected),
        "generation_case_list_hash": _hash_payload(generation_ids_by_category),
        "hard_constraints": {
            "soft_guidance_only": True,
            "exact_tool_choice": False,
            "argument_creation": False,
            "ctspc_v0_enabled": False,
            "old_repair_stack_enabled": False,
            "holdout_authorized": False,
            "hundred_case_authorized": False,
            "full_bfcl_authorized": False,
        },
        "pre_registered_checks": [
            "required capability observed before final_answer",
            "final answer uses retrieved content when memory retrieval is required",
            "controls have no false-positive activation",
            "BFCL scorer correct for positive cases",
        ],
        "blockers": blockers,
        "next_required_action": "request_separate_controlled_memory_heavy_smoke_approval" if ready else "repair_executable_protocol_mapping_before_smoke",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Explicit Obligation Executable Smoke Protocol",
        "",
        f"- BFCL executable manifest ready: `{report['bfcl_executable_manifest_ready']}`",
        f"- Selection method: `{report['selection_method']}`",
        f"- Positive / control cases: `{report['positive_case_count']}` / `{report['control_case_count']}`",
        f"- Selected case hash: `{report['selected_case_list_hash']}`",
        f"- Generation case hash: `{report['generation_case_list_hash']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Approval status: `{report['approval_status']}`",
        f"- Execution allowed: `{report['execution_allowed']}`",
        f"- Allowed provider profiles: `{report['allowed_provider_profiles']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This materialized protocol is still review-only. It does not authorize BFCL/model/scorer execution.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-audit", type=Path, default=DEFAULT_MEMORY_AUDIT)
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--positive-limit", type=int, default=12)
    parser.add_argument("--control-limit", type=int, default=8)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.memory_audit, args.source_root, args.positive_limit, args.control_limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        keys = [
            "bfcl_executable_manifest_ready",
            "positive_case_count",
            "control_case_count",
            "mapped_positive_candidate_count",
            "mapped_control_candidate_count",
            "selected_case_list_hash",
            "generation_case_list_hash",
            "candidate_commands",
            "planned_commands",
            "blockers",
            "next_required_action",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["bfcl_executable_manifest_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
