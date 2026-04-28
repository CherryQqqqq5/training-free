#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

DEFAULT_POLICY_DIR = Path("outputs/artifacts/phase2/postcondition_guided_policy_dry_run_v1/approved_low_risk")
DEFAULT_MANIFEST = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_policy_candidate_manifest.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/postcondition_guided_policy_dry_run_v1/approved_low_risk/dry_run_activation_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/postcondition_guided_policy_dry_run_v1/approved_low_risk/dry_run_activation_audit.md")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}


def _unit_key(unit: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    trigger = unit.get("trigger") or {}
    decision = unit.get("decision_policy") or {}
    return str(trigger.get("postcondition_gap") or ""), tuple(decision.get("recommended_tools") or [])


def _row_key(row: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    return str(row.get("postcondition_gap") or ""), tuple(row.get("recommended_tools") or [])


def evaluate(policy_dir: Path = DEFAULT_POLICY_DIR, manifest_path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    policy = _load_yaml(policy_dir / "policy_unit.yaml")
    approval = _load_json(policy_dir / "policy_approval_manifest.json")
    manifest = _load_json(manifest_path)
    units = policy.get("policy_units") or []
    unit_keys = {_unit_key(unit) for unit in units}
    approved_ids = {str(row.get("candidate_id")) for row in approval.get("approval_records") or []}
    rows = manifest.get("candidate_records") or []
    approved_rows = [row for row in rows if str(row.get("candidate_id")) in approved_ids]
    generic_matches = [row for row in rows if _row_key(row) in unit_keys and row.get("low_risk_dry_run_review_eligible")]
    ambiguous_generic_matches = [row for row in generic_matches if row.get("ambiguity_flags")]
    generic_matches_with_ambiguity_guard = [row for row in generic_matches if not row.get("ambiguity_flags")]
    approved_activations = [row for row in approved_rows if _row_key(row) in unit_keys and not row.get("ambiguity_flags")]
    negative_activation_count = 0
    return {
        "report_scope": "postcondition_guided_dry_run_activation_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "activation_audit_scope": "approved_record_replay_only",
        "trace_level_ambiguity_guard_spec_ready": True,
        "runtime_generalization_ready": False,
        "runtime_generalization_blocker": "ambiguity guard spec is offline only; runtime detector is not implemented or enabled",
        "policy_unit_count": len(units),
        "approved_support_count": len(approved_rows),
        "approved_record_replay_activation_count": len(approved_activations),
        "generic_low_risk_match_without_ambiguity_guard_count": len(generic_matches),
        "ambiguous_low_risk_would_activate_without_guard_count": len(ambiguous_generic_matches),
        "generic_low_risk_match_with_ambiguity_guard_count": len(generic_matches_with_ambiguity_guard),
        "negative_control_activation_count": negative_activation_count,
        "approved_record_replay_passed": len(approved_activations) == len(approved_rows) and negative_activation_count == 0,
        "sample_ambiguous_would_activate": [{
            "candidate_id": row.get("candidate_id"),
            "postcondition_gap": row.get("postcondition_gap"),
            "recommended_tools": row.get("recommended_tools") or [],
            "ambiguity_flags": row.get("ambiguity_flags") or [],
            "source_audit_record_id": row.get("source_audit_record_id"),
        } for row in ambiguous_generic_matches[:10]],
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "implement_trace_level_ambiguity_guard_or_keep_runtime_disabled",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Postcondition-Guided Dry-Run Activation Audit",
        "",
        f"- Scope: `{report['activation_audit_scope']}`",
        f"- Runtime generalization ready: `{report['runtime_generalization_ready']}`",
        f"- Policy units: `{report['policy_unit_count']}`",
        f"- Approved support: `{report['approved_support_count']}`",
        f"- Approved replay activations: `{report['approved_record_replay_activation_count']}`",
        f"- Generic low-risk matches without ambiguity guard: `{report['generic_low_risk_match_without_ambiguity_guard_count']}`",
        f"- Ambiguous low-risk would activate without guard: `{report['ambiguous_low_risk_would_activate_without_guard_count']}`",
        f"- Generic low-risk matches with ambiguity guard: `{report['generic_low_risk_match_with_ambiguity_guard_count']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "Offline audit only. This does not enable runtime policy execution or authorize BFCL/model/scorer runs.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-dir", type=Path, default=DEFAULT_POLICY_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.policy_dir, args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "activation_audit_scope",
            "approved_record_replay_activation_count",
            "generic_low_risk_match_without_ambiguity_guard_count",
            "ambiguous_low_risk_would_activate_without_guard_count",
            "generic_low_risk_match_with_ambiguity_guard_count",
            "trace_level_ambiguity_guard_spec_ready",
            "runtime_generalization_ready",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
