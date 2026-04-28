#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_AUDIT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/policy_conversion_opportunity_audit.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_policy_candidate_manifest.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_policy_family_card.md")

LOW_RISK_CAPABILITIES = {"read_content", "search_or_find"}
MEDIUM_RISK_CAPABILITIES = {"create_file", "write_content", "directory_navigation"}
HIGH_RISK_CAPABILITIES = {"copy", "move_or_rename"}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _risk(row: dict[str, Any]) -> tuple[str, str]:
    cap = str(row.get("postcondition_gap") or "")
    if cap in LOW_RISK_CAPABILITIES:
        return "low", "read_or_search_postcondition_with_local_witness"
    if cap in MEDIUM_RISK_CAPABILITIES:
        return "medium", "state_mutating_or_navigation_policy_requires_reviewer_approval"
    if cap in HIGH_RISK_CAPABILITIES:
        return "high", "copy_or_move_policy_is_trajectory_sensitive"
    return "unknown", "capability_not_in_reviewed_risk_table"


def evaluate(audit_path: Path = DEFAULT_AUDIT) -> dict[str, Any]:
    audit = _load(audit_path)
    rows = list(audit.get("candidate_records") or audit.get("sample_candidates") or [])
    manifest_rows = []
    for idx, row in enumerate(rows):
        risk, reason = _risk(row)
        retained = {
            "candidate_id": f"postcondition_guided_trajectory_policy_{idx:04d}",
            "trace_relative_path": row.get("trace_relative_path"),
            "run_name": row.get("run_name"),
            "policy_family": "postcondition_guided_trajectory_policy",
            "theory_class": "postcondition_guided_trajectory_progress",
            "postcondition_gap": row.get("postcondition_gap"),
            "recommended_tools": row.get("recommended_tools") or [],
            "expected_observation_keys": row.get("expected_observation_keys") or [],
            "request_predicates": row.get("request_predicates") or [],
            "failure_labels": row.get("failure_labels") or [],
            "precondition_observable": bool(row.get("precondition_observable")),
            "postcondition_witness_available": bool(row.get("postcondition_witness_available")),
            "target_or_scorer_field_dependency": bool(row.get("target_or_scorer_field_dependency")),
            "intervention_strength": "guidance_only",
            "exact_tool_choice": False,
            "retention_eligibility": "diagnostic_only_until_family_review",
            "risk_level": risk,
            "risk_reason": reason,
            "runtime_enabled": False,
            "requires_reviewer_approval_before_runtime": True,
        }
        manifest_rows.append(retained)
    risk_counts = Counter(row["risk_level"] for row in manifest_rows)
    cap_counts = Counter(str(row.get("postcondition_gap") or "unknown") for row in manifest_rows)
    return {
        "report_scope": "postcondition_guided_policy_candidate_manifest",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "runtime_enabled": False,
        "policy_family": "postcondition_guided_trajectory_policy",
        "theory_class": "postcondition_guided_trajectory_progress",
        "family_card_status": "review_required_before_runtime_integration",
        "admission_criteria": [
            "no_tool_policy_failure_label_present",
            "rule_hit_present",
            "prior_tool_observation_or_predicate_present",
            "recommended_tool_is_available_in_schema",
            "postcondition_witness_declared",
            "guidance_only",
            "exact_tool_choice_false",
            "no_target_or_scorer_field_dependency",
        ],
        "rejection_criteria": [
            "case_id_or_gold_answer_dependency",
            "recommended_tool_not_in_schema",
            "no_observable_prior_context",
            "destructive_or_state_mutating_tool_without_explicit_intent",
            "copy_move_or_directory_policy_without_reviewer_approval",
            "exact_tool_choice_required",
        ],
        "negative_controls_required": [
            "activation_near_zero_on_no_toolless_failure_slices",
            "activation_near_zero_when_required_postcondition_already_satisfied",
            "no_activation_without_available_recommended_tool",
        ],
        "candidate_count": len(manifest_rows),
        "risk_level_distribution": dict(sorted(risk_counts.items())),
        "capability_distribution": dict(sorted(cap_counts.items())),
        "candidate_records": manifest_rows,
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "delivery_and_research_review_before_compiler_or_runtime_integration",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Postcondition-Guided Trajectory Policy Family Card",
        "",
        "Status: `review_required_before_runtime_integration`",
        "",
        "This is an offline theory-prior family card. It does not enable runtime policy execution and does not authorize BFCL/model/scorer runs.",
        "",
        f"- Candidate count: `{report['candidate_count']}`",
        f"- Risk distribution: `{report['risk_level_distribution']}`",
        f"- Capability distribution: `{report['capability_distribution']}`",
        "",
        "## Theory Prior",
        "",
        "A tool-use trajectory should not terminate in prose when an unsatisfied, observable postcondition can be advanced by an available schema-local tool. The policy recommends a capability/tool family, not a case-specific tool call or argument value.",
        "",
        "## Admission Criteria",
        "",
    ]
    lines.extend(f"- `{item}`" for item in report["admission_criteria"])
    lines.extend(["", "## Rejection Criteria", ""])
    lines.extend(f"- `{item}`" for item in report["rejection_criteria"])
    lines.extend(["", "## Negative Controls Required", ""])
    lines.extend(f"- `{item}`" for item in report["negative_controls_required"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.audit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "family_card_status",
            "candidate_count",
            "risk_level_distribution",
            "capability_distribution",
            "runtime_enabled",
            "next_required_action",
        ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
