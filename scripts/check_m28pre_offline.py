#!/usr/bin/env python3
"""Aggregate M2.8-pre offline readiness gates."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DEFAULT_SUBSET = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_LOW_RISK = Path("outputs/artifacts/bfcl_explicit_required_arg_literal_v1")
OUT = DEFAULT_LOW_RISK / "m28pre_offline_summary.json"
MD = DEFAULT_LOW_RISK / "m28pre_offline_summary.md"

DEFAULT_REQUIRED_EXPLICIT_GENERATABLE = 35


def _j(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _no_commands(*items: dict[str, Any]) -> bool:
    return not any(item.get("planned_commands") or item.get("candidate_commands") for item in items)


def evaluate(subset_root: Path = DEFAULT_SUBSET, low_risk_root: Path = DEFAULT_LOW_RISK) -> dict[str, Any]:
    status = _j(subset_root / "m27ae_ctspc_v0_status.json", {}) or {}
    repair = _j(subset_root / "repair_stack_contribution.json", {}) or {}
    compiler = _j(low_risk_root / "compiler_summary.json", {}) or {}
    coverage = _j(low_risk_root / "retention_prior_coverage_audit.json", {}) or {}
    raw_coverage = _j(low_risk_root / "raw_bfcl_literal_coverage_audit.json", {}) or {}
    dev = _j(low_risk_root / "explicit_required_arg_literal_dev20_manifest.json", {}) or {}
    holdout = _j(low_risk_root / "explicit_required_arg_literal_holdout20_manifest.json", {}) or {}
    strat_dev = _j(low_risk_root / "stratified_low_risk_dev20_manifest.json", {}) or {}
    strat_holdout = _j(low_risk_root / "stratified_low_risk_holdout20_manifest.json", {}) or {}
    freeze = bool(
        status.get("ctspc_v0_frozen")
        and status.get("scorer_default") == "off"
        and status.get("retain") == 0
        and status.get("dev_rerun_authorized") is False
        and status.get("holdout_authorized") is False
    )
    dev_ids = set(str(x) for x in dev.get("selected_case_ids") or [])
    holdout_ids = set(str(x) for x in holdout.get("selected_case_ids") or [])
    strat_dev_ids = set(str(x) for x in strat_dev.get("selected_case_ids") or [])
    strat_holdout_ids = set(str(x) for x in strat_holdout.get("selected_case_ids") or [])
    explicit_disjoint = not (dev_ids & holdout_ids)
    stratified_disjoint = not (strat_dev_ids & strat_holdout_ids)
    compiler_ready = bool(compiler.get("compiler_ready") or compiler.get("m28pre_explicit_required_arg_literal_compiler_passed"))
    explicit_holdout_ready = bool(compiler.get("explicit_holdout_ready") or compiler.get("m28pre_explicit_required_arg_literal_holdout_ready")) and explicit_disjoint
    stratified_holdout_ready = bool(compiler.get("stratified_holdout_ready")) and stratified_disjoint
    no_scorer_commands = _no_commands(compiler, coverage, raw_coverage, dev, holdout, strat_dev, strat_holdout)
    retain_eligible_count = int(compiler.get("retain_eligible_candidate_count") or 0)
    required_generatable = int(compiler.get("required_explicit_candidate_generatable") or DEFAULT_REQUIRED_EXPLICIT_GENERATABLE)
    coverage_ready = bool(coverage.get("m28pre_retention_prior_coverage_audit_ready"))
    coverage_zero = bool(coverage.get("explicit_prior_family_coverage_zero"))
    coverage_current_count = int(coverage.get("current_context_anchored_literal_candidate_count") or 0)
    raw_ready = bool(raw_coverage.get("m28pre_raw_bfcl_literal_coverage_audit_ready"))
    raw_prompt_anchored_count = int(raw_coverage.get("source_result_literals_prompt_anchored_count") or 0)
    raw_zero = bool(raw_coverage.get("source_result_literals_prompt_coverage_zero"))
    safeguards = bool(
        compiler.get("ctspc_v0_action_rules_enabled") is False
        and compiler.get("ctspc_v0_file_path_multi_turn_enabled") is False
        and compiler.get("repair_stack_default") == "disabled"
        and compiler.get("candidate_rules_type") == "explicit_required_arg_literal_completion"
        and compiler.get("no_next_tool_intervention") is True
        and compiler.get("exact_tool_choice") is False
        and compiler.get("retention_prior_required") is True
        and retain_eligible_count >= required_generatable
    )
    explicit_family_ready = bool(
        explicit_holdout_ready
        and retain_eligible_count >= required_generatable
        and coverage_ready
        and not coverage_zero
        and coverage_current_count >= required_generatable
        and raw_ready
        and not raw_zero
    )
    checks = {
        "ctspc_v0_frozen": freeze,
        "repair_stack_split_ready": bool(repair.get("repair_stack_split_ready")),
        "compiler_ready": compiler_ready,
        "explicit_holdout_ready": explicit_holdout_ready,
        "stratified_holdout_ready": stratified_holdout_ready,
        "dev_holdout_disjoint": explicit_disjoint,
        "stratified_dev_holdout_disjoint": stratified_disjoint,
        "no_scorer_commands": no_scorer_commands,
        "runtime_manifest_safeguards_passed": safeguards,
        "retention_prior_coverage_audit_ready": coverage_ready,
        "explicit_prior_family_coverage_zero": coverage_zero,
        "raw_bfcl_literal_coverage_audit_ready": raw_ready,
        "explicit_prior_family_raw_prompt_coverage_zero": raw_zero,
        "explicit_family_scorer_authorization_ready": explicit_family_ready,
    }
    blockers: list[str] = []
    if not checks["ctspc_v0_frozen"]:
        blockers.append("ctspc_v0_not_frozen")
    if not checks["repair_stack_split_ready"]:
        blockers.append("repair_stack_split_not_ready")
    if not checks["compiler_ready"]:
        blockers.append("compiler_not_ready")
    if not checks["explicit_holdout_ready"]:
        blockers.append("explicit_holdout_not_ready")
    if not no_scorer_commands:
        blockers.append("scorer_commands_present")
    if not safeguards:
        blockers.append("runtime_manifest_safeguards_failed")
    if not coverage_ready:
        blockers.append("retention_prior_coverage_audit_missing")
    if coverage_zero:
        blockers.append("explicit_prior_family_coverage_zero")
    if coverage_current_count < required_generatable:
        blockers.append("explicit_current_context_coverage_below_35")
    if not raw_ready:
        blockers.append("raw_bfcl_literal_coverage_audit_missing")
    if raw_zero:
        blockers.append("explicit_prior_family_raw_prompt_coverage_zero")
    compiler_blockers = compiler.get("blockers") or []
    for blocker in compiler_blockers if isinstance(compiler_blockers, list) else []:
        if blocker not in blockers:
            blockers.append(str(blocker))
    scorer_authorization_ready = all([
        checks["ctspc_v0_frozen"],
        checks["repair_stack_split_ready"],
        checks["compiler_ready"],
        checks["no_scorer_commands"],
        checks["runtime_manifest_safeguards_passed"],
        checks["explicit_family_scorer_authorization_ready"],
    ])
    return {
        "report_scope": "m2_8pre_offline_summary",
        **checks,
        "source_result_literals_prompt_anchored_count": raw_prompt_anchored_count,
        "scorer_authorization_ready": scorer_authorization_ready,
        "m2_8pre_offline_passed": scorer_authorization_ready,
        "blockers": blockers,
        "compiler": {key: compiler.get(key) for key in [
            "selected_case_count",
            "candidate_generatable_count",
            "stratified_selected_case_count",
            "stratified_candidate_generatable_count",
            "ambiguous_literal_count",
            "stratified_ambiguous_literal_count",
            "source_pool_expansion_required",
            "explicit_source_pool_expansion_required",
            "stratified_source_pool_expansion_required",
            "required_explicit_total",
            "required_explicit_candidate_generatable",
            "required_stratified_total",
            "required_stratified_candidate_generatable",
            "blockers",
            "retention_prior_required",
            "retention_prior_rule_family",
            "retention_prior_distribution",
            "stratified_retention_prior_distribution",
            "retain_eligible_candidate_count",
            "stratified_retain_eligible_candidate_count",
            "theory_prior_explicit_literal_candidate_count",
        ]},
        "coverage_audit": {key: coverage.get(key) for key in [
            "m28pre_retention_prior_coverage_audit_ready",
            "coverage_bucket_counts",
            "current_context_anchored_literal_candidate_count",
            "source_result_only_diagnostic_candidate_count",
            "ambiguous_current_context_literal_candidate_count",
            "no_observable_literal_case_count",
            "explicit_prior_family_coverage_zero",
            "coverage_conclusion",
            "candidate_commands",
            "planned_commands",
        ]},
        "raw_bfcl_literal_coverage_audit": {key: raw_coverage.get(key) for key in [
            "m28pre_raw_bfcl_literal_coverage_audit_ready",
            "source_result_diagnostic_literal_count",
            "source_result_literals_prompt_anchored_count",
            "source_result_literals_retain_prior_candidate_count",
            "source_result_literals_prompt_coverage_zero",
            "failure_reason_counts",
            "route_recommendation",
            "pivot_to_next_theory_family",
            "candidate_commands",
            "planned_commands",
        ]},
        "dev_manifest": {key: dev.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "no_next_tool_intervention", "exact_tool_choice"]},
        "holdout_manifest": {key: holdout.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "no_next_tool_intervention", "exact_tool_choice"]},
        "stratified_dev_manifest": {key: strat_dev.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "no_next_tool_intervention", "exact_tool_choice"]},
        "stratified_holdout_manifest": {key: strat_holdout.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "no_next_tool_intervention", "exact_tool_choice"]},
        "diagnostic": {
            "offline_readiness_only": True,
            "does_not_authorize_scorer_without_separate_request": True,
            "no_bfcl_or_model_call": True,
            "stratified_pool_diagnostic_only_until_family_priors_exist": True,
            "bfcl_score_cannot_create_retain_rule": True,
            "raw_prompt_coverage_does_not_create_retain_rule": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M2.8-pre Offline Summary",
        "",
        f"- Passed: `{report['m2_8pre_offline_passed']}`",
        f"- Scorer authorization ready: `{report['scorer_authorization_ready']}`",
        f"- Raw prompt anchored source-result literals: `{report['source_result_literals_prompt_anchored_count']}`",
        f"- Blockers: `{report['blockers']}`",
        "",
        "| Check | Passed |",
        "| --- | ---: |",
    ]
    for key in [
        "ctspc_v0_frozen",
        "repair_stack_split_ready",
        "compiler_ready",
        "explicit_holdout_ready",
        "stratified_holdout_ready",
        "retention_prior_coverage_audit_ready",
        "explicit_prior_family_coverage_zero",
        "raw_bfcl_literal_coverage_audit_ready",
        "explicit_prior_family_raw_prompt_coverage_zero",
        "no_scorer_commands",
        "runtime_manifest_safeguards_passed",
    ]:
        lines.append(f"| `{key}` | `{report[key]}` |")
    lines.extend(["", "Offline readiness only. No scorer command is emitted by this artifact.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset-root", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--low-risk-root", type=Path, default=DEFAULT_LOW_RISK)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.subset_root, args.low_risk_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({key: report.get(key) for key in [
            "m2_8pre_offline_passed",
            "scorer_authorization_ready",
            "ctspc_v0_frozen",
            "repair_stack_split_ready",
            "compiler_ready",
            "explicit_holdout_ready",
            "retention_prior_coverage_audit_ready",
            "explicit_prior_family_coverage_zero",
            "raw_bfcl_literal_coverage_audit_ready",
            "explicit_prior_family_raw_prompt_coverage_zero",
            "source_result_literals_prompt_anchored_count",
            "no_scorer_commands",
            "blockers",
        ]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
