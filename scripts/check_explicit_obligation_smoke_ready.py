#!/usr/bin/env python3
"""Canonical readiness gate for explicit-obligation smoke execution.

This checker aggregates executable materialization, baseline dry audit,
selection audit, artifact boundary, and M2.8-pre scorer authorization. It never
runs BFCL/model/scorer and never emits execution commands.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import scripts.check_artifact_boundary as artifact_boundary
from scripts.check_m28pre_offline import evaluate as evaluate_m28pre

DEFAULT_EXECUTABLE = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_executable_smoke_protocol.json")
DEFAULT_DRY = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_baseline_dry_audit.json")
DEFAULT_SELECTION = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_smoke_selection_audit.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_smoke_ready.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/explicit_obligation_observable_capability_v1/explicit_obligation_smoke_ready.md")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _artifact_boundary_status() -> dict[str, Any]:
    bad = artifact_boundary.forbidden_outputs(artifact_boundary.collect_output_paths(tracked_only=False))
    return {
        "artifact_boundary_passed": not bad,
        "forbidden_artifact_count": len(bad),
        "forbidden_artifact_samples": bad[:50],
    }


def _prefer_present_int(primary: dict[str, Any], key: str, fallback: dict[str, Any] | None = None, fallback_key: str | None = None) -> int:
    if key in primary:
        return int(primary.get(key) or 0)
    if fallback is not None:
        return int(fallback.get(fallback_key or key) or 0)
    return 0


def evaluate(executable_path: Path = DEFAULT_EXECUTABLE, dry_path: Path = DEFAULT_DRY, selection_path: Path = DEFAULT_SELECTION) -> dict[str, Any]:
    executable = _load_json(executable_path) or {}
    dry = _load_json(dry_path) or {}
    selection = _load_json(selection_path) or {}
    artifact_status = _artifact_boundary_status()
    m28 = evaluate_m28pre()
    gates = {
        "bfcl_executable_manifest_ready": bool(executable.get("bfcl_executable_manifest_ready")),
        "smoke_selection_ready_after_baseline_dry_audit": bool(dry.get("smoke_selection_ready_after_baseline_dry_audit")),
        "selection_gate_passed": bool(selection.get("selection_gate_passed")),
        "artifact_boundary_passed": bool(artifact_status.get("artifact_boundary_passed")),
        "scorer_authorization_ready": bool(m28.get("scorer_authorization_ready")),
        "candidate_commands_empty": not bool(executable.get("candidate_commands") or dry.get("candidate_commands") or selection.get("candidate_commands")),
        "planned_commands_empty": not bool(executable.get("planned_commands") or dry.get("planned_commands") or selection.get("planned_commands")),
    }
    blockers: list[str] = []
    if not gates["bfcl_executable_manifest_ready"]:
        blockers.append("bfcl_executable_manifest_not_ready")
    if not gates["smoke_selection_ready_after_baseline_dry_audit"]:
        blockers.append("smoke_selection_not_ready_after_baseline_dry_audit")
    if selection and not gates["selection_gate_passed"]:
        blockers.append("selection_gate_not_passed")
    if not gates["artifact_boundary_passed"]:
        blockers.append("artifact_boundary_not_passed")
    if not gates["scorer_authorization_ready"]:
        blockers.append("scorer_authorization_not_ready")
    if not gates["candidate_commands_empty"]:
        blockers.append("candidate_commands_present")
    if not gates["planned_commands_empty"]:
        blockers.append("planned_commands_present_before_approval")
    for blocker in selection.get("blockers") or []:
        blocker = str(blocker)
        if blocker not in blockers:
            blockers.append(blocker)
    for blocker in dry.get("blockers") or []:
        blocker = str(blocker)
        if blocker not in blockers:
            blockers.append(blocker)
    ready = bool(all(gates.values()) and not blockers)
    next_required_actions: list[str] = []
    if not gates["bfcl_executable_manifest_ready"]:
        next_required_actions.append("rebuild_bfcl_executable_manifest")
    if not gates["smoke_selection_ready_after_baseline_dry_audit"] or not gates["selection_gate_passed"]:
        next_required_actions.append("rebuild_candidate_pool_or_upgrade_theory_prior_before_smoke")
    if not gates["artifact_boundary_passed"]:
        next_required_actions.append("clean_or_move_forbidden_artifacts_before_smoke")
    if not gates["scorer_authorization_ready"]:
        next_required_actions.append("repair_m2_8pre_scorer_authorization_before_smoke")
    if not gates["candidate_commands_empty"] or not gates["planned_commands_empty"]:
        next_required_actions.append("remove_execution_commands_until_approval")
    if ready:
        next_required_actions = ["request_explicit_smoke_execution_approval"]
    next_action = next_required_actions[0] if next_required_actions else "repair_explicit_smoke_readiness_blockers"
    return {
        "report_scope": "explicit_obligation_smoke_ready",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "ready": ready,
        "execution_allowed": False,
        "gates": gates,
        "artifact_boundary": artifact_status,
        "scorer_authorization_ready": gates["scorer_authorization_ready"],
        "selection_gate_passed": gates["selection_gate_passed"],
        "selected_smoke_baseline_control_activation_count": _prefer_present_int(selection, "selected_smoke_baseline_control_activation_count", dry),
        "source_pool_negative_control_activation_count": int(selection.get("source_pool_negative_control_activation_count") or 0),
        "materialized_protocol_negative_control_activation_count": int(selection.get("materialized_protocol_negative_control_activation_count") or 0),
        "blockers": blockers,
        "next_required_action": next_action,
        "next_required_actions": next_required_actions,
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Explicit Obligation Smoke Ready",
        "",
        f"- Ready: `{report['ready']}`",
        f"- Execution allowed: `{report['execution_allowed']}`",
        f"- Gates: `{report['gates']}`",
        f"- Source-pool negative-control activations: `{report['source_pool_negative_control_activation_count']}`",
        f"- Materialized protocol negative-control activations: `{report['materialized_protocol_negative_control_activation_count']}`",
        f"- Selected smoke baseline control activations: `{report['selected_smoke_baseline_control_activation_count']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        f"- Next required actions: `{report['next_required_actions']}`",
        "",
        "This checker is offline-only. It does not authorize BFCL/model/scorer execution.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXECUTABLE)
    parser.add_argument("--dry-audit", type=Path, default=DEFAULT_DRY)
    parser.add_argument("--selection", type=Path, default=DEFAULT_SELECTION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.executable, args.dry_audit, args.selection)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        keys = ["ready", "execution_allowed", "gates", "selected_smoke_baseline_control_activation_count", "source_pool_negative_control_activation_count", "materialized_protocol_negative_control_activation_count", "candidate_commands", "planned_commands", "blockers", "next_required_action", "next_required_actions"]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
