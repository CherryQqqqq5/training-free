#!/usr/bin/env python3
"""Build a review-only smoke protocol for explicit-obligation capability prior.

This writes a protocol manifest. It does not run BFCL/model/scorer and emits no
executable scorer commands. A future smoke requires separate approval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

DEFAULT_AUDIT = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_observable_capability_audit.json")
DEFAULT_MEMORY = Path("outputs/artifacts/phase2/memory_operation_obligation_v1/memory_operation_obligation_audit.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_smoke_protocol.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_smoke_protocol.md")


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _select_memory_positive(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    rows = []
    for item in memory.get("candidate_records") or []:
        if not isinstance(item, dict):
            continue
        if item.get("candidate_ready") is True and item.get("risk_level") == "low" and item.get("operation") == "retrieve":
            rows.append({
                "case_id": item.get("candidate_id"),
                "category": item.get("category"),
                "trace_relative_path": item.get("trace_relative_path"),
                "capability_family": "memory_retrieve",
                "expected_policy": "soft_guidance_only_memory_retrieve",
                "exact_tool_choice": False,
                "argument_creation": False,
                "source_record_pointer": item.get("source_audit_record_pointer_debug_only"),
            })
        if len(rows) >= limit:
            break
    return rows


def _select_memory_controls(memory: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    controls = []
    seen_reasons: set[str] = set()
    for item in memory.get("sample_rejections") or []:
        if not isinstance(item, dict):
            continue
        reason = str(item.get("rejection_reason") or item.get("review_rejection_reason") or "unknown")
        if reason in seen_reasons and len(controls) >= limit:
            continue
        seen_reasons.add(reason)
        controls.append({
            "case_id": item.get("source_audit_record_id"),
            "category": item.get("category"),
            "trace_relative_path": item.get("trace_relative_path"),
            "negative_control_type": reason,
            "expected_activation": False,
            "exact_tool_choice": False,
            "argument_creation": False,
        })
        if len(controls) >= limit:
            break
    return controls


def evaluate(audit_path: Path = DEFAULT_AUDIT, memory_path: Path = DEFAULT_MEMORY) -> dict[str, Any]:
    audit = _load(audit_path)
    memory = _load(memory_path)
    eligible_by_cap = audit.get("eligible_by_capability") or {}
    memory_count = int(eligible_by_cap.get("memory_retrieve") or 0)
    read_count = int(eligible_by_cap.get("read_content") or 0)
    positive = _select_memory_positive(memory, 12)
    controls = _select_memory_controls(memory, 8)
    coverage_imbalance = bool(memory_count and memory_count / max(1, sum(int(v) for v in eligible_by_cap.values())) > 0.8)
    protocol_ready = bool(audit.get("smoke_ready") and len(positive) >= 12 and len(controls) >= 6)
    candidate_payload = json.dumps({"positive": positive, "controls": controls}, ensure_ascii=False, sort_keys=True)
    frozen_candidate_hash = hashlib.sha256(candidate_payload.encode("utf-8")).hexdigest()
    blockers = []
    if len(positive) < 12:
        blockers.append("positive_memory_cases_below_12")
    if len(controls) < 6:
        blockers.append("control_cases_below_6")
    if not audit.get("smoke_ready"):
        blockers.append("explicit_obligation_audit_not_smoke_ready")
    return {
        "report_scope": "explicit_obligation_smoke_protocol",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "protocol_id": "explicit_obligation_memory_heavy_smoke_v1",
        "smoke_protocol_version": "v1",
        "future_provider_profile": "novacode",
        "future_model_route": "gpt-5.4",
        "allowed_provider_profiles": ["novacode"],
        "future_profile_only": True,
        "separate_approval_required_before_execution": True,
        "approval_status": "pending",
        "execution_mode": "audit_only_protocol",
        "execution_allowed": False,
        "admission_gate": "fail_closed",
        "runtime_gate": "disabled_until_approved",
        "candidate_set_frozen": True,
        "frozen_candidate_count": len(positive) + len(controls),
        "frozen_candidate_hash": frozen_candidate_hash,
        "protocol_ready_for_review": protocol_ready,
        "protocol_lane": "memory_heavy_first_smoke",
        "coverage_imbalance_memory_heavy": coverage_imbalance,
        "eligible_by_capability": eligible_by_cap,
        "positive_case_count": len(positive),
        "control_case_count": len(controls),
        "positive_cases": positive,
        "control_cases": controls,
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
        "stop_loss_gate": {
            "control_activation_count": 0,
            "exact_tool_choice_count": 0,
            "argument_creation_count": 0,
            "case_regressed_count_max": 0,
            "net_case_gain_min": 1,
            "candidate_accuracy_must_exceed_baseline": True,
        },
        "formal_pass_gate": {
            "candidate_accuracy_delta_pp_min": 3.0,
            "case_fixed_greater_than_regressed": True,
            "case_regressed_count_max": 0,
            "holdout_required_for_retain": True,
        },
        "blockers": blockers,
        "next_required_action": "request_separate_memory_heavy_smoke_approval" if protocol_ready else "repair_protocol_selection_before_smoke",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Explicit Obligation Smoke Protocol",
        "",
        f"- Protocol ready for review: `{report['protocol_ready_for_review']}`",
        f"- Protocol lane: `{report['protocol_lane']}`",
        f"- Memory-heavy imbalance: `{report['coverage_imbalance_memory_heavy']}`",
        f"- Positive / control cases: `{report['positive_case_count']}` / `{report['control_case_count']}`",
        f"- Future provider profile: `{report['future_provider_profile']}`",
        f"- Separate approval required: `{report['separate_approval_required_before_execution']}`",
        f"- Approval status: `{report['approval_status']}`",
        f"- Execution allowed: `{report['execution_allowed']}`",
        f"- Candidate set frozen/hash: `{report['candidate_set_frozen']}` / `{report['frozen_candidate_hash']}`",
        f"- Allowed provider profiles: `{report['allowed_provider_profiles']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Stop-loss gate: `{report['stop_loss_gate']}`",
        f"- Formal pass gate: `{report['formal_pass_gate']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "Offline protocol only. It does not authorize BFCL/model/scorer runs.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--memory", type=Path, default=DEFAULT_MEMORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.audit, args.memory)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "protocol_ready_for_review": report["protocol_ready_for_review"],
            "protocol_lane": report["protocol_lane"],
            "coverage_imbalance_memory_heavy": report["coverage_imbalance_memory_heavy"],
            "positive_case_count": report["positive_case_count"],
            "control_case_count": report["control_case_count"],
            "separate_approval_required_before_execution": report["separate_approval_required_before_execution"],
            "approval_status": report["approval_status"],
            "execution_allowed": report["execution_allowed"],
            "candidate_set_frozen": report["candidate_set_frozen"],
            "frozen_candidate_hash": report["frozen_candidate_hash"],
            "candidate_commands": report["candidate_commands"],
            "planned_commands": report["planned_commands"],
            "next_required_action": report["next_required_action"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
