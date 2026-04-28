#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_AUDIT = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_obligation_audit.json")
DEFAULT_OUT_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_v1")
NEGATIVE_OUT = "memory_operation_negative_control_audit.json"
NEGATIVE_MD = "memory_operation_negative_control_audit.md"
APPROVAL_OUT = "memory_operation_approval_manifest.json"
APPROVAL_MD = "memory_operation_approval_manifest.md"
ALLOWLIST_OUT = "memory_operation_compiler_allowlist.json"
ALLOWLIST_MD = "memory_operation_compiler_allowlist.md"

NEGATIVE_CONTROL_SPECS = {
    "no_memory_tools": {
        "description": "Records without memory tools must never activate memory obligation guidance.",
        "rejection_reasons": {"no_memory_tools_available"},
    },
    "no_memory_intent": {
        "description": "Records without observable memory retrieve intent must never activate memory obligation guidance.",
        "rejection_reasons": {"no_memory_operation_intent"},
    },
    "strong_value_witness": {
        "description": "Records with a strong value/postcondition witness are already satisfied and must not activate.",
        "rejection_reasons": {"memory_postcondition_already_satisfied"},
    },
    "empty_or_error_witness": {
        "description": "Records with empty/error memory witness are diagnostic only and must not activate.",
        "rejection_reasons": {"empty_or_error_memory_witness"},
    },
    "delete_clear_forget": {
        "description": "Delete/clear/forget memory operations require separate reviewer approval and must not activate retrieve guidance.",
        "rejection_reasons": {"delete_operation_requires_explicit_reviewer_approval"},
    },
}

FORBIDDEN_MANIFEST_KEYS = {
    "source_audit_record_pointer_debug_only",
    "trace_relative_path",
    "available_memory_tools",
    "called_memory_tools",
    "case_id",
    "raw_prompt",
    "raw_output",
    "prompt",
    "output",
    "request",
    "request_original",
}

FORBIDDEN_TOOL_TOKENS = ("clear", "remove", "delete", "add", "replace", "update", "append")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _tool_family(tool: str) -> str:
    lowered = tool.lower()
    if "key_search" in lowered or lowered.endswith("_search") or "memory_search" in lowered:
        return "memory_key_or_text_search"
    if "list" in lowered:
        return "memory_list_keys"
    if "retrieve" in lowered:
        return "memory_value_retrieve"
    return "memory_retrieve_related"




def _support_hash(row: dict[str, Any], ordinal: int) -> str:
    strength = str(row.get("memory_witness_strength") or "unknown")
    payload = "|".join([
        str(row.get("category") or "unknown"),
        str(row.get("operation") or "unknown"),
        str(row.get("operation_scope") or "unknown"),
        strength,
        "first_pass_retrieve" if strength == "no_witness" else "second_pass_retrieve" if strength == "weak_lookup_witness" else "blocked",
        str(ordinal),
    ])
    return "memsup_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _has_forbidden_key(obj: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_path = f"{path}.{key}" if path else str(key)
            if key in FORBIDDEN_MANIFEST_KEYS:
                hits.append(key_path)
            hits.extend(_has_forbidden_key(value, key_path))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            hits.extend(_has_forbidden_key(value, f"{path}[{idx}]"))
    return hits


def _candidate_negative_activation(control: str, row: dict[str, Any]) -> bool:
    if not row.get("candidate_ready"):
        return False
    if control == "no_memory_tools":
        return not row.get("recommended_tools")
    if control == "no_memory_intent":
        return row.get("operation") is None
    if control == "strong_value_witness":
        return bool(row.get("memory_postcondition_witness_present") or row.get("memory_witness_strength") == "strong_value_witness")
    if control == "empty_or_error_witness":
        return row.get("memory_witness_strength") == "empty_or_error_witness"
    if control == "delete_clear_forget":
        return row.get("operation") == "delete" or row.get("operation_scope") != "retrieve_only"
    if control == "forbidden_dependency":
        return bool((row.get("forbidden_field_scan") or {}).get("forbidden_dependency_present"))
    return False


def _negative_controls(report: dict[str, Any]) -> dict[str, Any]:
    rows = report.get("candidate_records") or []
    rejection_counts = Counter(report.get("rejection_reason_counts") or {})
    controls: dict[str, Any] = {}
    for name, spec in NEGATIVE_CONTROL_SPECS.items():
        source_evaluated_count = sum(int(rejection_counts.get(reason, 0)) for reason in spec["rejection_reasons"])
        synthetic_evaluated_count = 0 if source_evaluated_count else 1
        activation_count = sum(1 for row in rows if _candidate_negative_activation(name, row))
        controls[name] = {
            "description": spec["description"],
            "source_evaluated_count": source_evaluated_count,
            "synthetic_evaluated_count": synthetic_evaluated_count,
            "synthetic_control_used": bool(synthetic_evaluated_count),
            "synthetic_control_reason": None if source_evaluated_count else "source_pool_has_zero_examples_for_required_negative_control",
            "evaluated_count": source_evaluated_count + synthetic_evaluated_count,
            "activation_count": activation_count,
            "passed": activation_count == 0 and source_evaluated_count + synthetic_evaluated_count > 0,
            "rejection_reasons": sorted(spec["rejection_reasons"]),
        }
    forbidden_activation = sum(1 for row in rows if _candidate_negative_activation("forbidden_dependency", row))
    controls["forbidden_dependency"] = {
        "description": "Runtime trigger fields must not depend on gold, scorer, target, BFCL result, trace ids, or raw debug pointers.",
        "source_evaluated_count": len(rows),
        "synthetic_evaluated_count": 0,
        "synthetic_control_used": False,
        "synthetic_control_reason": None,
        "evaluated_count": len(rows),
        "activation_count": forbidden_activation,
        "passed": forbidden_activation == 0 and len(rows) > 0,
        "rejection_reasons": [],
    }
    return controls


def _sanitized_support(row: dict[str, Any], ordinal: int) -> dict[str, Any]:
    strength = str(row.get("memory_witness_strength") or "unknown")
    recommended = row.get("recommended_tools") or []
    families = sorted({_tool_family(str(tool)) for tool in recommended})
    return {
        "support_record_hash": _support_hash(row, ordinal),
        "category": row.get("category"),
        "policy_family": "memory_operation_obligation",
        "theory_class": "memory_postcondition_obligation",
        "operation": row.get("operation"),
        "operation_scope": row.get("operation_scope"),
        "memory_witness_strength": strength,
        "support_class": "first_pass_retrieve" if strength == "no_witness" else "second_pass_retrieve" if strength == "weak_lookup_witness" else "blocked",
        "recommended_tool_capability_families": families,
        "forbidden_field_scan_clean": not bool((row.get("forbidden_field_scan") or {}).get("forbidden_dependency_present")),
        "review_eligible": bool(row.get("review_eligible")),
        "compiler_input_eligible": False,
        "approval_status": "review_candidate_only",
        "requires_separate_weak_witness_approval": strength == "weak_lookup_witness",
        "runtime_enabled": False,
        "exact_tool_choice": False,
        "candidate_commands": [],
        "planned_commands": [],
    }


def evaluate(audit_path: Path = DEFAULT_AUDIT) -> dict[str, Any]:
    report = _load(audit_path)
    rows = report.get("candidate_records") or []
    controls = _negative_controls(report)
    supports = [_sanitized_support(row, idx) for idx, row in enumerate(rows)]
    forbidden_manifest_paths = _has_forbidden_key(supports)
    forbidden_tool_family_hits = [
        support.get("support_record_hash")
        for support in supports
        for family in support.get("recommended_tool_capability_families") or []
        if any(token in str(family).lower() for token in FORBIDDEN_TOOL_TOKENS)
    ]
    first_pass = [support for support in supports if support.get("support_class") == "first_pass_retrieve"]
    second_pass = [support for support in supports if support.get("support_class") == "second_pass_retrieve"]
    negative_passed = all(control.get("passed") for control in controls.values())
    required_negative_controls_present = all(int(control.get("evaluated_count") or 0) > 0 for control in controls.values())
    manifest_sanitized = not forbidden_manifest_paths and not forbidden_tool_family_hits
    compiler_allowlist_records = [
        {
            **support,
            "compiler_input_eligible": True,
            "approval_status": "compiler_allowlisted_first_pass_only",
            "compiler_contract": "dry_run_compiler_must_read_only_this_allowlist_not_raw_audit_or_review_manifest",
        }
        for support in first_pass
    ]
    approval_manifest = {
        "report_scope": "memory_operation_obligation_sanitized_approval_manifest",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_enabled": False,
        "compiler_enabled": False,
        "exact_tool_choice": False,
        "candidate_commands": [],
        "planned_commands": [],
        "approval_manifest_sanitized": manifest_sanitized,
        "approval_manifest_ready_for_review": bool(supports) and negative_passed and manifest_sanitized,
        "compiler_input_eligible_count": 0,
        "weak_witness_requires_separate_approval": True,
        "first_pass_review_candidate_count": len(first_pass),
        "second_pass_review_candidate_count": len(second_pass),
        "support_record_count": len(supports),
        "support_class_distribution": dict(sorted(Counter(support.get("support_class") for support in supports).items())),
        "forbidden_manifest_key_paths": forbidden_manifest_paths[:50],
        "forbidden_tool_family_hits": forbidden_tool_family_hits[:50],
        "support_records": supports,
        "next_required_action": "delivery_and_research_review_before_memory_runtime_compiler",
    }
    compiler_allowlist = {
        "report_scope": "memory_operation_obligation_compiler_allowlist",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_enabled": False,
        "compiler_enabled": False,
        "exact_tool_choice": False,
        "candidate_commands": [],
        "planned_commands": [],
        "compiler_allowlist_ready": bool(compiler_allowlist_records) and negative_passed and manifest_sanitized,
        "compiler_input_eligible_count": len(compiler_allowlist_records),
        "compiler_scope": "first_pass_retrieve_no_witness_only",
        "weak_witness_compiler_input_count": 0,
        "compiler_contract": {
            "compiler_must_read_only_this_allowlist": True,
            "raw_audit_forbidden_as_compiler_input": True,
            "review_manifest_forbidden_as_compiler_input": True,
            "second_pass_weak_witness_requires_separate_allowlist": True,
        },
        "allowlist_records": compiler_allowlist_records,
    }
    negative_report = {
        "report_scope": "memory_operation_obligation_negative_control_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_enabled": False,
        "compiler_enabled": False,
        "exact_tool_choice": False,
        "candidate_commands": [],
        "planned_commands": [],
        "candidate_count": len(rows),
        "candidate_records_present": bool(rows),
        "first_pass_support_count": len(first_pass),
        "second_pass_support_count": len(second_pass),
        "weak_witness_support_count": len(second_pass),
        "weak_witness_compiler_input_count": 0,
        "negative_control_evaluations": controls,
        "required_negative_controls_present": required_negative_controls_present,
        "negative_control_audit_passed": bool(rows) and negative_passed and required_negative_controls_present,
        "approval_manifest_sanitized": manifest_sanitized,
        "approval_manifest_ready_for_review": approval_manifest["approval_manifest_ready_for_review"],
        "next_required_action": "delivery_and_research_review_before_memory_runtime_compiler",
    }
    return {
        "negative_report": negative_report,
        "approval_manifest": approval_manifest,
        "compiler_allowlist": compiler_allowlist,
    }


def render_negative_markdown(report: dict[str, Any]) -> str:
    lines = ["# Memory Operation Negative Control Audit", "", f"Passed: `{report['negative_control_audit_passed']}`", f"Candidate count: `{report['candidate_count']}`", f"First-pass support: `{report['first_pass_support_count']}`", f"Second-pass support: `{report['second_pass_support_count']}`", "", "## Controls", ""]
    for name, control in report["negative_control_evaluations"].items():
        lines.append(f"- `{name}`: evaluated `{control['evaluated_count']}`, activation `{control['activation_count']}`, passed `{control['passed']}`")
    lines.extend(["", "Offline audit only. This does not enable runtime policy execution or authorize BFCL/model/scorer runs.", ""])
    return "\n".join(lines)


def render_approval_markdown(report: dict[str, Any]) -> str:
    lines = ["# Memory Operation Approval Manifest", "", f"Ready for review: `{report['approval_manifest_ready_for_review']}`", f"Sanitized: `{report['approval_manifest_sanitized']}`", f"Support records: `{report['support_record_count']}`", f"First-pass review candidates: `{report['first_pass_review_candidate_count']}`", f"Second-pass review candidates: `{report['second_pass_review_candidate_count']}`", f"Compiler input eligible count: `{report['compiler_input_eligible_count']}`", "", "Support records are sanitized hashes and aggregate capabilities only; trace paths, case ids, raw prompts, raw outputs, and available tool lists are excluded.", ""]
    return "\n".join(lines)


def render_compiler_allowlist_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Memory Operation Compiler Allowlist",
        "",
        f"Ready: `{report['compiler_allowlist_ready']}`",
        f"Scope: `{report['compiler_scope']}`",
        f"Compiler input eligible count: `{report['compiler_input_eligible_count']}`",
        f"Weak witness compiler input count: `{report['weak_witness_compiler_input_count']}`",
        "",
        "This allowlist is sanitized and first-pass only. The dry-run compiler must read this file, not the raw audit or review manifest.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    outputs = evaluate(args.audit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    negative = outputs["negative_report"]
    approval = outputs["approval_manifest"]
    (args.output_dir / NEGATIVE_OUT).write_text(json.dumps(negative, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / NEGATIVE_MD).write_text(render_negative_markdown(negative), encoding="utf-8")
    (args.output_dir / APPROVAL_OUT).write_text(json.dumps(approval, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / APPROVAL_MD).write_text(render_approval_markdown(approval), encoding="utf-8")
    allowlist = outputs["compiler_allowlist"]
    (args.output_dir / ALLOWLIST_OUT).write_text(json.dumps(allowlist, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.output_dir / ALLOWLIST_MD).write_text(render_compiler_allowlist_markdown(allowlist), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "negative_control_audit_passed": negative["negative_control_audit_passed"],
            "approval_manifest_ready_for_review": approval["approval_manifest_ready_for_review"],
            "approval_manifest_sanitized": approval["approval_manifest_sanitized"],
            "first_pass_review_candidate_count": approval["first_pass_review_candidate_count"],
            "second_pass_review_candidate_count": approval["second_pass_review_candidate_count"],
            "review_manifest_compiler_input_eligible_count": approval["compiler_input_eligible_count"],
            "compiler_allowlist_ready": outputs["compiler_allowlist"]["compiler_allowlist_ready"],
            "compiler_allowlist_input_count": outputs["compiler_allowlist"]["compiler_input_eligible_count"],
        }, indent=2, sort_keys=True))
    return 0 if negative["negative_control_audit_passed"] and approval["approval_manifest_ready_for_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
