#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

DEFAULT_SOURCE_ROOT = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1")
DEFAULT_OUT_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_v1")
MEMORY_CATEGORIES = ("memory_kv", "memory_rec_sum", "memory_vector")
RETRIEVE_TOOLS = ("memory_retrieve", "core_memory_retrieve", "core_memory_retrieve_all", "archival_memory_retrieve", "archival_memory_key_search", "core_memory_key_search", "memory_search")
WRITE_TOOLS = ("memory_append", "memory_update", "memory_replace", "core_memory_add", "core_memory_replace", "archival_memory_add", "archival_memory_replace")
DELETE_TOOLS = ("memory_clear", "memory_remove", "core_memory_clear", "core_memory_remove", "archival_memory_clear", "archival_memory_remove")
LIST_TOOLS = ("memory_list", "core_memory_list_keys", "archival_memory_list_keys")
VALUE_KEYS = {"value", "content", "text", "answer", "context", "record", "records", "memory"}
WEAK_KEYS = {"keys", "matches", "results"}


def _load(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _trace_files(source_root: Path) -> list[Path]:
    files: list[Path] = []
    for category in MEMORY_CATEGORIES:
        root = source_root / category / "baseline" / "traces"
        if root.exists():
            files.extend(sorted(root.glob("*.json")))
    return files


def _request(payload: dict[str, Any]) -> dict[str, Any]:
    return payload.get("request_original") if isinstance(payload.get("request_original"), dict) else (payload.get("request") or {})


def _messages(request: dict[str, Any]) -> list[dict[str, Any]]:
    raw = request.get("input") or request.get("messages") or []
    return [item for item in raw if isinstance(item, dict)]


def _available_tools(request: dict[str, Any]) -> list[str]:
    tools = []
    for item in request.get("tools") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or (item.get("function") or {}).get("name")
        if isinstance(name, str):
            tools.append(name)
    return sorted(dict.fromkeys(tools))


def _user_text(request: dict[str, Any]) -> str:
    return "\n".join(str(msg.get("content")) for msg in _messages(request) if msg.get("role") == "user" and isinstance(msg.get("content"), str))


def _called_tools(request: dict[str, Any]) -> list[str]:
    return [str(msg.get("name")) for msg in _messages(request) if msg.get("type") == "function_call" and msg.get("name")]


def _tool_outputs(request: dict[str, Any]) -> list[str]:
    outs = []
    for msg in _messages(request):
        if msg.get("type") == "function_call_output" or msg.get("role") == "tool":
            raw = msg.get("output", msg.get("content"))
            if raw is not None:
                outs.append(str(raw))
    return outs


def _has_any(names: Iterable[str], needles: Iterable[str]) -> bool:
    names_l = [name.lower() for name in names]
    return any(any(needle in name for needle in needles) for name in names_l)


def _infer_operation(text: str) -> tuple[str | None, str | None]:
    lowered = text.lower()
    if re.search(r"\b(forget|delete|remove|clear)\b", lowered):
        return "delete", "delete_or_forget_cue"
    if re.search(r"\b(remember|save|store|note|keep track|my preference|i prefer)\b", lowered):
        return "write", "durable_fact_or_preference_cue"
    if re.search(r"\b(what|which|how much|when|where|who|remind|recall|look up|do i|did i)\b", lowered):
        return "retrieve", "memory_recall_question_cue"
    return None, None


def _recommended_tools(operation: str, available: list[str]) -> list[str]:
    if operation == "retrieve":
        pool = RETRIEVE_TOOLS + LIST_TOOLS
    elif operation == "write":
        pool = WRITE_TOOLS
    elif operation == "delete":
        pool = DELETE_TOOLS
    else:
        return []
    available_set = set(available)
    return [tool for tool in pool if tool in available_set]


def _jsonish_outputs(outputs: list[str]) -> list[Any]:
    parsed = []
    for raw in outputs:
        try:
            parsed.append(json.loads(raw))
        except Exception:
            parsed.append(raw)
    return parsed


def _flatten_keys(obj: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.add(str(key).lower())
            keys.update(_flatten_keys(value))
    elif isinstance(obj, list):
        for item in obj:
            keys.update(_flatten_keys(item))
    return keys


def _witness_strength(operation: str, called: list[str], outputs: list[str]) -> tuple[str, list[str]]:
    called_l = [name.lower() for name in called]
    out_text = "\n".join(outputs).lower()
    parsed = _jsonish_outputs(outputs)
    keys = set().union(*(_flatten_keys(item) for item in parsed)) if parsed else set()
    if not _has_any(called_l, RETRIEVE_TOOLS + LIST_TOOLS + WRITE_TOOLS + DELETE_TOOLS):
        return "no_witness", []
    if "error during execution" in out_text or "not found" in out_text or "division by zero" in out_text or out_text.strip() in {"", "[]", "{}"}:
        return "empty_or_error_witness", ["memory_tool_error_or_empty_output"]
    if operation == "retrieve":
        if keys & VALUE_KEYS:
            return "strong_value_witness", sorted(keys & VALUE_KEYS)
        if keys & WEAK_KEYS or _has_any(called_l, LIST_TOOLS):
            return "weak_lookup_witness", sorted((keys & WEAK_KEYS) or {"memory_list_or_key_search_call"})
    if operation == "write" and _has_any(called_l, WRITE_TOOLS):
        return "strong_value_witness", ["memory_write_call_observed"]
    if operation == "delete" and _has_any(called_l, DELETE_TOOLS):
        return "strong_value_witness", ["memory_delete_call_observed"]
    return "weak_lookup_witness", ["memory_call_observed_without_value_witness"]


def _category(path: Path) -> str:
    parts = path.parts
    for category in MEMORY_CATEGORIES:
        if category in parts:
            return category
    return "unknown"


def _audit_id(rel: str, operation: str | None) -> str:
    return "memop_" + hashlib.sha256(f"{rel}|{operation}".encode("utf-8")).hexdigest()[:16]


def _forbidden_scan(record: dict[str, Any]) -> dict[str, Any]:
    trigger = {
        "operation": record.get("operation"),
        "operation_cue": record.get("operation_cue"),
        "recommended_tools": record.get("recommended_tools") or [],
        "memory_witness_strength": record.get("memory_witness_strength"),
    }
    text = json.dumps(trigger, sort_keys=True).lower()
    forbidden_tokens = [token for token in ["gold", "scorer", "target", "bfcl_result"] if token in text]
    return {
        "runtime_trigger_fields_scanned": sorted(trigger),
        "gold_or_scorer_token_in_trigger_logic": bool(forbidden_tokens),
        "forbidden_tokens": forbidden_tokens,
        "trace_id_in_trigger_logic": bool(re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)),
        "forbidden_dependency_present": bool(forbidden_tokens),
        "audit_pointers_excluded_from_runtime_fields": True,
    }


def _record(path: Path, source_root: Path) -> dict[str, Any] | None:
    payload = _load(path)
    if not isinstance(payload, dict):
        return None
    request = _request(payload)
    available = _available_tools(request)
    memory_available = any("memory" in tool.lower() for tool in available)
    text = _user_text(request)
    operation, cue = _infer_operation(text)
    called = _called_tools(request)
    outputs = _tool_outputs(request)
    strength, witness_keys = _witness_strength(operation or "", called, outputs)
    recommended = _recommended_tools(operation or "", available)
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    rejection_reason = None
    if not memory_available:
        rejection_reason = "no_memory_tools_available"
    elif operation is None:
        rejection_reason = "no_memory_operation_intent"
    elif operation == "delete":
        rejection_reason = "delete_operation_requires_explicit_reviewer_approval"
    elif operation != "retrieve":
        rejection_reason = "non_retrieve_operation_not_yet_evidenced"
    elif not recommended:
        rejection_reason = "no_schema_available_memory_tool_for_operation"
    elif strength == "strong_value_witness":
        rejection_reason = "memory_postcondition_already_satisfied"
    elif strength == "empty_or_error_witness":
        rejection_reason = "empty_or_error_memory_witness"
    rel = _safe_relative(path, source_root)
    candidate_ready = rejection_reason is None
    record = {
        "source_audit_record_id": _audit_id(rel, operation),
        "source_audit_record_pointer_debug_only": rel,
        "trace_relative_path": rel,
        "category": _category(path),
        "operation": operation,
        "operation_scope": "retrieve_only" if operation == "retrieve" else "non_retrieve_blocked",
        "operation_cue": cue,
        "available_memory_tools": [tool for tool in available if "memory" in tool.lower()],
        "recommended_tools": recommended,
        "called_memory_tools": [tool for tool in called if "memory" in tool.lower()],
        "memory_witness_strength": strength,
        "memory_postcondition_witness_present": strength == "strong_value_witness",
        "memory_postcondition_witnesses": witness_keys,
        "failure_labels": validation.get("failure_labels") or [],
        "repair_kinds": validation.get("repair_kinds") or [],
        "candidate_ready": candidate_ready,
        "review_eligible": candidate_ready,
        "low_risk_dry_run_review_eligible": candidate_ready,
        "compiler_input_eligible": False,
        "risk_level": "low" if candidate_ready else "blocked",
        "policy_family": "memory_operation_obligation" if candidate_ready else None,
        "theory_class": "memory_postcondition_obligation" if candidate_ready else None,
        "retention_eligibility": "diagnostic_only_until_family_review" if candidate_ready else "never_retain",
        "runtime_enabled": False,
        "exact_tool_choice": False,
        "rejection_reason": rejection_reason,
        "review_rejection_reason": None if candidate_ready else rejection_reason,
        "candidate_commands": [],
        "planned_commands": [],
    }
    record["forbidden_field_scan"] = _forbidden_scan(record)
    return record


def evaluate(source_root: Path = DEFAULT_SOURCE_ROOT) -> dict[str, Any]:
    records = [row for path in _trace_files(source_root) if (row := _record(path, source_root)) is not None]
    for idx, row in enumerate(records):
        if row.get("candidate_ready"):
            row["candidate_id"] = f"memory_operation_obligation_{idx:04d}"
    candidates = [row for row in records if row.get("candidate_ready")]
    return {
        "report_scope": "memory_operation_obligation_family_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_enabled": False,
        "family_card_status": "review_required_before_runtime_integration",
        "policy_family": "memory_operation_obligation",
        "theory_class": "memory_postcondition_obligation",
        "theory_prior": "When durable memory facts are requested and memory tools are schema-available, the agent should not answer from prose before an observable retrieve memory postcondition is satisfied.",
        "admission_criteria": ["memory_tools_available", "retrieve_intent_observable_in_current_user_turn", "matching_memory_retrieve_tool_available_in_schema", "strong_memory_postcondition_witness_absent", "guidance_only", "exact_tool_choice_false", "no_gold_or_target_dependency"],
        "rejection_criteria": ["delete_or_clear_operation_without_reviewer_approval", "write_family_not_yet_evidenced", "no_observable_memory_intent", "memory_postcondition_already_satisfied", "empty_or_error_memory_witness", "no_schema_available_memory_tool_for_operation", "hidden_target_or_gold_value_dependency", "argument_or_memory_value_creation"],
        "negative_controls_required": ["no_activation_without_memory_tools", "no_activation_without_memory_intent", "no_activation_when_memory_postcondition_already_satisfied", "delete_false_positive_count_zero"],
        "trace_count": len(records),
        "candidate_count": len(candidates),
        "category_distribution": dict(sorted(Counter(row.get("category") for row in records).items())),
        "candidate_category_distribution": dict(sorted(Counter(row.get("category") for row in candidates).items())),
        "operation_distribution": dict(sorted(Counter(str(row.get("operation") or "unknown") for row in records).items())),
        "candidate_operation_distribution": dict(sorted(Counter(str(row.get("operation") or "unknown") for row in candidates).items())),
        "memory_witness_strength_distribution": dict(sorted(Counter(str(row.get("memory_witness_strength") or "unknown") for row in records).items())),
        "candidate_witness_strength_distribution": dict(sorted(Counter(str(row.get("memory_witness_strength") or "unknown") for row in candidates).items())),
        "rejection_reason_counts": dict(sorted(Counter(str(row.get("rejection_reason") or "candidate_ready") for row in records).items())),
        "candidate_records": candidates,
        "sample_candidates": candidates[:20],
        "sample_rejections": [row for row in records if not row.get("candidate_ready")][:20],
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "delivery_and_research_review_before_memory_runtime_compiler",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Memory Operation Obligation Family Card", "", "Status: `review_required_before_runtime_integration`", "", f"- Trace count: `{report['trace_count']}`", f"- Candidate count: `{report['candidate_count']}`", f"- Candidate operation distribution: `{report['candidate_operation_distribution']}`", f"- Candidate category distribution: `{report['candidate_category_distribution']}`", f"- Witness strength distribution: `{report['memory_witness_strength_distribution']}`", f"- Rejection reasons: `{report['rejection_reason_counts']}`", "", "## Theory Prior", "", report["theory_prior"], "", "## Admission Criteria", ""]
    lines.extend(f"- `{item}`" for item in report["admission_criteria"])
    lines.extend(["", "## Rejection Criteria", ""])
    lines.extend(f"- `{item}`" for item in report["rejection_criteria"])
    lines.extend(["", "## Negative Controls Required", ""])
    lines.extend(f"- `{item}`" for item in report["negative_controls_required"])
    lines.extend(["", "Offline audit only. This does not enable runtime policy execution or authorize BFCL/model/scorer runs.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE_ROOT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.source_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "memory_operation_obligation_audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / "memory_operation_obligation_family_card.md").write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in ["family_card_status", "trace_count", "candidate_count", "candidate_operation_distribution", "candidate_category_distribution", "memory_witness_strength_distribution", "rejection_reason_counts", "runtime_enabled", "next_required_action"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
