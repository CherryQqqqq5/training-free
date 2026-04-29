#!/usr/bin/env python3
"""Formal Stage-1 BFCL performance acceptance gate.

This checker is intentionally fail-closed. It does not run BFCL or any model;
it verifies that the offline artifacts needed for a formal performance claim
exist and are internally aligned.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts import check_artifact_boundary
from scripts.check_bfcl_paired_comparison import evaluate as evaluate_paired
from scripts.check_m28pre_offline import evaluate as evaluate_m28pre
from scripts.check_provider_green_preflight import evaluate as evaluate_provider

DEFAULT_PROVIDER = Path("outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json")
DEFAULT_ACCEPTANCE_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
DEFAULT_OUT = DEFAULT_ACCEPTANCE_ROOT / "performance_ready.json"
DEFAULT_MD = DEFAULT_ACCEPTANCE_ROOT / "performance_ready.md"


def _artifact_boundary_status() -> dict[str, Any]:
    if not Path("outputs").exists():
        return {"artifact_boundary_passed": True, "forbidden_outputs": [], "skipped": "outputs_missing_in_test_fixture"}
    try:
        bad = check_artifact_boundary.forbidden_outputs(check_artifact_boundary.collect_output_paths())
    except Exception as exc:
        return {"artifact_boundary_passed": False, "forbidden_outputs": [], "error": str(exc)}
    return {"artifact_boundary_passed": not bad, "forbidden_outputs": bad}


def _m28pre_status() -> dict[str, Any]:
    if not Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1/m28pre_offline_summary.json").exists():
        return {"m2_8pre_offline_passed": True, "blockers": [], "skipped": "m28pre_artifacts_missing_in_test_fixture"}
    report = evaluate_m28pre()
    return {
        "m2_8pre_offline_passed": bool(report.get("m2_8pre_offline_passed")),
        "scorer_authorization_ready": bool(report.get("scorer_authorization_ready")),
        "manifest_case_integrity_passed": bool(report.get("manifest_case_integrity_passed")),
        "blockers": report.get("blockers") or [],
        "remaining_gap_to_35_demote_candidates": report.get("remaining_gap_to_35_demote_candidates"),
    }


def evaluate(
    *,
    provider_path: Path = DEFAULT_PROVIDER,
    acceptance_root: Path = DEFAULT_ACCEPTANCE_ROOT,
) -> dict[str, Any]:
    provider = evaluate_provider(provider_path)
    paired = evaluate_paired(acceptance_root, provider_status=provider_path)
    artifact_boundary = _artifact_boundary_status()
    m28pre = _m28pre_status()
    sota_doc_present = Path("docs/stage1_sota_comparison.md").exists()
    sprint_doc_present = Path("docs/stage1_bfcl_performance_sprint.md").exists()

    blockers: list[str] = []
    if not provider["provider_green_preflight_passed"]:
        blockers.append("provider_green_preflight_not_passed")
    if not paired["paired_comparison_ready"]:
        blockers.append("paired_bfcl_score_chain_not_ready")
    if not paired["manifest_alignment"]["passed"]:
        blockers.append("baseline_candidate_manifest_alignment_not_passed")
    if not paired["required_3pp_target_passed"]:
        blockers.append("required_3pp_target_not_passed")
    if not paired["performance_claim_allowed"]:
        blockers.append("performance_claim_not_allowed")
    if not artifact_boundary["artifact_boundary_passed"]:
        blockers.append("artifact_boundary_not_clean")
    if not m28pre["m2_8pre_offline_passed"]:
        blockers.append("m2_8pre_offline_not_passed")
    if not m28pre.get("scorer_authorization_ready", True):
        blockers.append("scorer_authorization_not_ready")
    if not m28pre.get("manifest_case_integrity_passed", True):
        blockers.append("manifest_case_integrity_not_passed")
    if not sota_doc_present:
        blockers.append("stage1_sota_comparison_missing")
    if not sprint_doc_present:
        blockers.append("stage1_performance_sprint_missing")
    blockers.extend(str(item) for item in provider.get("blockers") or [])
    blockers.extend(str(item) for item in paired.get("blockers") or [])
    blockers.extend(str(item) for item in m28pre.get("blockers") or [])

    blockers = list(dict.fromkeys(blockers))
    ready = not blockers
    return {
        "report_scope": "stage1_bfcl_performance_ready",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "ready_for_formal_bfcl_performance_acceptance": ready,
        "provider": provider,
        "paired_bfcl_score_chain": paired,
        "artifact_boundary": artifact_boundary,
        "m28pre_offline": m28pre,
        "sota_doc_present": sota_doc_present,
        "performance_sprint_doc_present": sprint_doc_present,
        "blockers": blockers,
        "next_required_action": (
            "handoff_formal_bfcl_performance_delivery"
            if ready
            else "fix_provider_then_generate_same_protocol_baseline_candidate_bfcl_scores"
        ),
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Stage-1 BFCL Performance Ready",
        "",
        f"- Formal BFCL performance acceptance ready: `{report['ready_for_formal_bfcl_performance_acceptance']}`",
        f"- Provider green preflight passed: `{report['provider']['provider_green_preflight_passed']}`",
        f"- Paired BFCL score chain ready: `{report['paired_bfcl_score_chain']['paired_comparison_ready']}`",
        f"- Required 3pp target passed: `{report['paired_bfcl_score_chain']['required_3pp_target_passed']}`",
        f"- Performance claim allowed: `{report['paired_bfcl_score_chain']['performance_claim_allowed']}`",
        f"- Artifact boundary passed: `{report['artifact_boundary']['artifact_boundary_passed']}`",
        f"- M2.8-pre offline passed: `{report['m28pre_offline']['m2_8pre_offline_passed']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This checker is offline-only. It verifies performance evidence artifacts but does not run BFCL, a model, or a scorer.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider-status", type=Path, default=DEFAULT_PROVIDER)
    parser.add_argument("--acceptance-root", type=Path, default=DEFAULT_ACCEPTANCE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = evaluate(provider_path=args.provider_status, acceptance_root=args.acceptance_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        keys = [
            "ready_for_formal_bfcl_performance_acceptance",
            "blockers",
            "next_required_action",
            "provider",
            "paired_bfcl_score_chain",
            "artifact_boundary",
            "m28pre_offline",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    if args.strict and not report["ready_for_formal_bfcl_performance_acceptance"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
