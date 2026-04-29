#!/usr/bin/env python3
"""Canonical first-stage BFCL delivery readiness gate.

This checker is intentionally stricter than the diagnostic delivery audit. It
answers one acceptance question: can this checkout be handed over as a
BFCL-first first-stage performance delivery? It does not run BFCL, a model, or
any scorer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.audit_delivery_evidence import evaluate as evaluate_delivery
from scripts.check_explicit_obligation_smoke_ready import evaluate as evaluate_explicit_smoke
from scripts.check_m28pre_offline import evaluate as evaluate_m28pre
from scripts.check_stage1_bfcl_performance_ready import evaluate as evaluate_performance

DEFAULT_OUT = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1/first_stage_bfcl_ready.json")
DEFAULT_MD = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1/first_stage_bfcl_ready.md")


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


MAINLINE_DELIVERY_BLOCKERS = {
    "artifact_boundary_not_clean",
    "m2_8pre_offline_not_passed",
    "scorer_authorization_not_ready",
}


def evaluate() -> dict[str, Any]:
    delivery = evaluate_delivery()
    m28 = evaluate_m28pre()
    explicit_smoke = evaluate_explicit_smoke()
    performance = evaluate_performance()

    gates = {
        "bfcl_first_protocol_documented": Path("docs/experiment_protocol_bfcl_v4.md").exists(),
        "acceptance_matrix_present": Path("docs/first_stage_acceptance_matrix.md").exists(),
        "algorithm_report_present": Path("docs/algorithm_report_v1.md").exists(),
        "theory_priors_present": Path("docs/theory_priors_for_first_stage.md").exists(),
        "artifact_boundary_passed": bool(delivery.get("artifact_boundary", {}).get("artifact_boundary_passed")),
        "m2_8pre_offline_passed": bool(m28.get("m2_8pre_offline_passed")),
        "manifest_case_integrity_passed": bool(m28.get("manifest_case_integrity_passed")),
        "scorer_authorization_ready": bool(m28.get("scorer_authorization_ready")),
        "sota_3pp_claim_ready": bool(delivery.get("sota_3pp_claim_ready")),
        "formal_bfcl_performance_ready": bool(performance.get("ready_for_formal_bfcl_performance_acceptance")),
    }
    secondary_gates = {
        "explicit_obligation_smoke_ready": bool(explicit_smoke.get("ready")),
    }

    blockers: list[str] = []
    if not gates["acceptance_matrix_present"]:
        blockers.append("acceptance_matrix_missing")
    if not gates["algorithm_report_present"]:
        blockers.append("algorithm_report_missing")
    if not gates["theory_priors_present"]:
        blockers.append("theory_priors_missing")
    if not gates["artifact_boundary_passed"]:
        blockers.append("artifact_boundary_not_clean")
    if not gates["m2_8pre_offline_passed"]:
        blockers.append("m2_8pre_offline_not_passed")
    if not gates["manifest_case_integrity_passed"]:
        blockers.append("manifest_case_integrity_not_passed")
    if not gates["scorer_authorization_ready"]:
        blockers.append("scorer_authorization_not_ready")
    if not gates["sota_3pp_claim_ready"]:
        blockers.append("sota_3pp_claim_not_ready")
    if not gates["formal_bfcl_performance_ready"]:
        blockers.append("formal_bfcl_performance_evidence_not_ready")

    delivery_p0_blockers = [str(item) for item in delivery.get("p0_blockers") or []]
    blockers.extend(item for item in delivery_p0_blockers if item in MAINLINE_DELIVERY_BLOCKERS)
    blockers.extend(str(item) for item in m28.get("blockers") or [])
    blockers.extend(str(item) for item in performance.get("blockers") or [])
    secondary_blockers = []
    secondary_blockers.extend(item for item in delivery_p0_blockers if item not in MAINLINE_DELIVERY_BLOCKERS)
    if not secondary_gates["explicit_obligation_smoke_ready"]:
        secondary_blockers.append("explicit_obligation_smoke_not_ready")
    secondary_blockers.extend(str(item) for item in explicit_smoke.get("blockers") or [])

    ready_for_huawei_acceptance = bool(all(gates.values()) and not blockers)
    ready_for_scaffold_handoff = bool(
        gates["bfcl_first_protocol_documented"]
        and gates["acceptance_matrix_present"]
        and gates["algorithm_report_present"]
        and gates["theory_priors_present"]
    )

    next_required_actions: list[str] = []
    if not gates["artifact_boundary_passed"]:
        next_required_actions.append("clean_or_move_forbidden_artifacts_outside_outputs")
    if not gates["m2_8pre_offline_passed"] or not gates["scorer_authorization_ready"]:
        next_required_actions.append("expand_deterministic_argument_repair_pool_and_rebuild_dev_holdout_manifests")
    if not secondary_gates["explicit_obligation_smoke_ready"]:
        next_required_actions.append("do_not_run_current_memory_heavy_explicit_obligation_smoke")
    if not gates["sota_3pp_claim_ready"]:
        next_required_actions.append("produce_reproducible_same_protocol_bfcl_dev_holdout_or_full_suite_gain")
    if not gates["formal_bfcl_performance_ready"]:
        next_required_actions.append("fix_provider_then_generate_same_protocol_baseline_candidate_bfcl_scores")
    if ready_for_huawei_acceptance:
        next_required_actions = ["handoff_first_stage_bfcl_performance_delivery"]
    elif not next_required_actions:
        next_required_actions = ["repair_first_stage_readiness_blockers"]

    return {
        "report_scope": "first_stage_bfcl_ready",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "ready_for_huawei_acceptance": ready_for_huawei_acceptance,
        "ready_for_scaffold_handoff": ready_for_scaffold_handoff,
        "delivery_claim_status": delivery.get("delivery_claim_status"),
        "gates": gates,
        "secondary_gates": secondary_gates,
        "mainline_delivery_blocker_kinds": sorted(MAINLINE_DELIVERY_BLOCKERS),
        "blockers": _unique(blockers),
        "secondary_blockers": _unique(secondary_blockers),
        "m28pre": {
            "remaining_gap_to_35_demote_candidates": m28.get("remaining_gap_to_35_demote_candidates"),
            "route_recommendation": m28.get("route_recommendation"),
        },
        "formal_performance": {
            "ready": performance.get("ready_for_formal_bfcl_performance_acceptance"),
            "next_required_action": performance.get("next_required_action"),
            "blockers": performance.get("blockers"),
        },
        "explicit_obligation": {
            "ready": explicit_smoke.get("ready"),
            "execution_allowed": explicit_smoke.get("execution_allowed"),
            "next_required_action": explicit_smoke.get("next_required_action"),
        },
        "next_required_action": next_required_actions[0],
        "next_required_actions": next_required_actions,
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# First-Stage BFCL Ready",
        "",
        f"- Huawei acceptance ready: `{report['ready_for_huawei_acceptance']}`",
        f"- Scaffold handoff ready: `{report['ready_for_scaffold_handoff']}`",
        f"- Claim status: `{report['delivery_claim_status']}`",
        f"- Gates: `{report['gates']}`",
        f"- Secondary gates: `{report['secondary_gates']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Secondary blockers: `{report['secondary_blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        f"- Next required actions: `{report['next_required_actions']}`",
        "",
        "This checker is offline-only and does not authorize BFCL/model/scorer execution.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        keys = [
            "ready_for_huawei_acceptance",
            "ready_for_scaffold_handoff",
            "delivery_claim_status",
            "gates",
            "secondary_gates",
            "blockers",
            "secondary_blockers",
            "next_required_action",
            "next_required_actions",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    if args.strict and not report["ready_for_huawei_acceptance"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
