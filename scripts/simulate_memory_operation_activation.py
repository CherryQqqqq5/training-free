#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_POLICY_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_dry_run_v1/first_pass")
DEFAULT_RESOLVER = DEFAULT_POLICY_DIR / "memory_tool_family_resolver_audit.json"
DEFAULT_NEGATIVE = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_negative_control_audit.json")
DEFAULT_APPROVAL = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_approval_manifest.json")
DEFAULT_OUT = DEFAULT_POLICY_DIR / "memory_operation_activation_simulation.json"
DEFAULT_MD = DEFAULT_POLICY_DIR / "memory_operation_activation_simulation.md"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def evaluate(resolver_path: Path = DEFAULT_RESOLVER, negative_path: Path = DEFAULT_NEGATIVE, approval_path: Path = DEFAULT_APPROVAL) -> dict[str, Any]:
    resolver = _load(resolver_path)
    negative = _load(negative_path)
    approval = _load(approval_path)
    activation_records = []
    blocked_records = []
    for record in resolver.get("resolver_records") or []:
        resolved_tool_count = sum(len(items) for items in (record.get("resolved_tool_families") or {}).values())
        base = {
            "support_record_hash": record.get("support_record_hash"),
            "category": record.get("category"),
            "policy_unit_id": record.get("policy_unit_id"),
            "argument_policy": record.get("argument_policy"),
            "exact_tool_choice": record.get("exact_tool_choice"),
            "runtime_enabled": record.get("runtime_enabled"),
            "resolved_tool_family_count": len(record.get("resolved_tool_families") or {}),
            "resolved_tool_count": resolved_tool_count,
        }
        if (
            record.get("policy_unit_id") == "memory_first_pass_retrieve_soft_v1"
            and record.get("argument_policy") == "no_argument_creation_or_binding"
            and record.get("exact_tool_choice") is False
            and record.get("runtime_enabled") is False
            and resolved_tool_count > 0
        ):
            activation_records.append({**base, "activated": True, "activation_reason": "first_pass_no_witness_with_schema_local_memory_tools"})
        else:
            blocked_records.append({**base, "activated": False, "block_reason": "activation_precondition_failed"})
    controls = negative.get("negative_control_evaluations") or {}
    negative_control_activation_count = sum(int(control.get("activation_count") or 0) for control in controls.values())
    weak_lookup_activation_count = int(resolver.get("weak_witness_records_resolved_count") or 0)
    upstream_gate_status = {
        "resolver_audit_passed": resolver.get("resolver_audit_passed") is True,
        "negative_control_audit_passed": negative.get("negative_control_audit_passed") is True,
        "approval_manifest_ready_for_review": approval.get("approval_manifest_ready_for_review") is True,
        "approval_manifest_sanitized": approval.get("approval_manifest_sanitized") is True,
        "review_manifest_compiler_input_eligible_zero": int(approval.get("compiler_input_eligible_count") or 0) == 0,
        "resolver_weak_witness_records_resolved_zero": weak_lookup_activation_count == 0,
    }
    upstream_gates_passed = all(upstream_gate_status.values())
    simulation_passed = bool(activation_records) and not blocked_records and negative_control_activation_count == 0 and upstream_gates_passed
    return {
        "report_scope": "memory_operation_runtime_like_activation_simulation",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_enabled": False,
        "exact_tool_choice": False,
        "argument_creation_count": 0,
        "candidate_commands": [],
        "planned_commands": [],
        "activation_simulation_passed": simulation_passed,
        "upstream_gates_passed": upstream_gates_passed,
        "upstream_gate_status": upstream_gate_status,
        "activation_records_diagnostic_only": True,
        "runtime_must_not_read_activation_records": True,
        "policy_unit_id": "memory_first_pass_retrieve_soft_v1",
        "activation_count": len(activation_records),
        "blocked_count": len(blocked_records),
        "negative_control_activation_count": negative_control_activation_count,
        "weak_lookup_witness_activation_count": weak_lookup_activation_count,
        "second_pass_review_candidate_count": int(approval.get("second_pass_review_candidate_count") or 0),
        "recommended_tool_capability_families": resolver.get("requested_capability_families") or [],
        "intervention_strength": "guidance_only",
        "activation_records": activation_records,
        "blocked_records": blocked_records[:50],
        "negative_control_evaluations": controls,
        "next_required_action": "memory_only_dev_scorer_requires_separate_approval_after_delivery_review",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Memory Operation Activation Simulation",
        "",
        f"Passed: `{report['activation_simulation_passed']}`",
        f"Activation count: `{report['activation_count']}`",
        f"Blocked count: `{report['blocked_count']}`",
        f"Negative-control activation count: `{report['negative_control_activation_count']}`",
        f"Upstream gates passed: `{report['upstream_gates_passed']}`",
        f"Weak lookup activation count: `{report['weak_lookup_witness_activation_count']}`",
        f"Runtime enabled: `{report['runtime_enabled']}`",
        f"Argument creation count: `{report['argument_creation_count']}`",
        "",
        "Offline simulation only. This does not run BFCL/model/scorer and does not enable runtime policy execution.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--resolver", type=Path, default=DEFAULT_RESOLVER)
    parser.add_argument("--negative", type=Path, default=DEFAULT_NEGATIVE)
    parser.add_argument("--approval", type=Path, default=DEFAULT_APPROVAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.resolver, args.negative, args.approval)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "activation_simulation_passed",
            "activation_count",
            "blocked_count",
            "negative_control_activation_count",
            "upstream_gates_passed",
            "weak_lookup_witness_activation_count",
            "argument_creation_count",
            "runtime_enabled",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    return 0 if report["activation_simulation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
