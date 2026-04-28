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
    availability = _j(low_risk_root / "m28pre_source_result_availability_audit.json", {}) or {}
    alias_coverage = _j(low_risk_root / "wrong_arg_key_alias_coverage_audit.json", {}) or {}
    deterministic_coverage = _j(low_risk_root / "deterministic_schema_local_coverage_audit.json", {}) or {}
    dev = _j(low_risk_root / "explicit_required_arg_literal_dev20_manifest.json", {}) or {}
    holdout = _j(low_risk_root / "explicit_required_arg_literal_holdout20_manifest.json", {}) or {}
    alias_dev = _j(low_risk_root / "wrong_arg_key_alias_dev20_manifest.json", {}) or {}
    alias_holdout = _j(low_risk_root / "wrong_arg_key_alias_holdout20_manifest.json", {}) or {}
    deterministic_dev = _j(low_risk_root / "deterministic_schema_local_dev20_manifest.json", {}) or {}
    deterministic_holdout = _j(low_risk_root / "deterministic_schema_local_holdout20_manifest.json", {}) or {}
    combined_dev = _j(low_risk_root / "theory_prior_low_risk_dev20_manifest.json", {}) or {}
    combined_holdout = _j(low_risk_root / "theory_prior_low_risk_holdout20_manifest.json", {}) or {}
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
    alias_dev_ids = set(str(x) for x in alias_dev.get("selected_case_ids") or [])
    alias_holdout_ids = set(str(x) for x in alias_holdout.get("selected_case_ids") or [])
    deterministic_dev_ids = set(str(x) for x in deterministic_dev.get("selected_case_ids") or [])
    deterministic_holdout_ids = set(str(x) for x in deterministic_holdout.get("selected_case_ids") or [])
    combined_dev_ids = set(str(x) for x in combined_dev.get("selected_case_ids") or []) or dev_ids
    combined_holdout_ids = set(str(x) for x in combined_holdout.get("selected_case_ids") or []) or holdout_ids
    strat_dev_ids = set(str(x) for x in strat_dev.get("selected_case_ids") or [])
    strat_holdout_ids = set(str(x) for x in strat_holdout.get("selected_case_ids") or [])
    explicit_disjoint = not (dev_ids & holdout_ids)
    alias_disjoint = not (alias_dev_ids & alias_holdout_ids)
    deterministic_disjoint = not (deterministic_dev_ids & deterministic_holdout_ids)
    combined_disjoint = not (combined_dev_ids & combined_holdout_ids)
    stratified_disjoint = not (strat_dev_ids & strat_holdout_ids)

    compiler_ready = bool(compiler.get("compiler_ready") or compiler.get("m28pre_explicit_required_arg_literal_compiler_passed"))
    explicit_holdout_ready = bool(compiler.get("explicit_holdout_ready") or compiler.get("m28pre_explicit_required_arg_literal_holdout_ready")) and explicit_disjoint
    alias_holdout_ready = bool(compiler.get("wrong_arg_key_alias_holdout_ready")) and alias_disjoint
    deterministic_holdout_ready = bool(compiler.get("deterministic_schema_local_holdout_ready")) and deterministic_disjoint
    combined_holdout_ready = bool(compiler.get("combined_theory_prior_holdout_ready", compiler.get("explicit_holdout_ready") or compiler.get("m28pre_explicit_required_arg_literal_holdout_ready"))) and combined_disjoint
    stratified_holdout_ready = bool(compiler.get("stratified_holdout_ready")) and stratified_disjoint
    no_scorer_commands = _no_commands(compiler, coverage, raw_coverage, availability, alias_coverage, deterministic_coverage, dev, holdout, alias_dev, alias_holdout, deterministic_dev, deterministic_holdout, combined_dev, combined_holdout, strat_dev, strat_holdout)

    explicit_retain_count = int(compiler.get("retain_eligible_candidate_count") or 0)
    alias_retain_count = int(compiler.get("wrong_arg_key_alias_demote_candidate_count") or 0)
    deterministic_retain_count = int(compiler.get("deterministic_schema_local_demote_candidate_count") or 0)
    combined_retain_count = int(compiler.get("combined_retain_eligible_candidate_count") or explicit_retain_count + deterministic_retain_count)
    required_generatable = int(compiler.get("required_explicit_candidate_generatable") or DEFAULT_REQUIRED_EXPLICIT_GENERATABLE)
    coverage_ready = bool(coverage.get("m28pre_retention_prior_coverage_audit_ready"))
    coverage_zero = bool(coverage.get("explicit_prior_family_coverage_zero"))
    coverage_current_count = int(coverage.get("current_context_anchored_literal_candidate_count") or 0)
    raw_ready = bool(raw_coverage.get("m28pre_raw_bfcl_literal_coverage_audit_ready"))
    raw_prompt_anchored_count = int(raw_coverage.get("source_result_literals_prompt_anchored_count") or 0)
    raw_zero = bool(raw_coverage.get("source_result_literals_prompt_coverage_zero"))
    availability_audit_ready = bool(availability.get("source_result_availability_audit_ready"))
    source_result_availability_ready = bool(availability.get("source_result_availability_ready"))
    alias_coverage_ready = bool(alias_coverage.get("wrong_arg_key_alias_coverage_audit_ready"))
    alias_family_coverage_zero = bool(alias_coverage.get("wrong_arg_key_alias_family_coverage_zero"))
    deterministic_coverage_ready = bool(deterministic_coverage.get("deterministic_schema_local_coverage_audit_ready"))
    deterministic_family_coverage_zero = bool(deterministic_coverage.get("deterministic_schema_local_family_coverage_zero"))
    remaining_gap_to_35 = max(0, required_generatable - combined_retain_count)
    prior_scan_category_coverage = compiler.get("prior_scan_category_coverage") or {}
    alias_scan_category_coverage = compiler.get("alias_scan_category_coverage") or {}
    compiler_category_coverage = compiler.get("compiler_category_coverage") or {}
    route_recommendation = deterministic_coverage.get("route_recommendation") or alias_coverage.get("route_recommendation") or compiler.get("route_recommendation")

    allowed_families = {"explicit_required_arg_literal_completion", "wrong_arg_key_alias_repair", "deterministic_schema_local_non_live_repair"}
    families = set(str(f) for f in (compiler.get("authorized_theory_prior_families") or []))
    if not families and compiler.get("candidate_rules_type") == "explicit_required_arg_literal_completion":
        families = {"explicit_required_arg_literal_completion"}
    safeguards = bool(
        compiler.get("ctspc_v0_action_rules_enabled") is False
        and compiler.get("ctspc_v0_file_path_multi_turn_enabled") is False
        and compiler.get("repair_stack_default") == "disabled"
        and families <= allowed_families
        and compiler.get("no_next_tool_intervention") is True
        and compiler.get("exact_tool_choice") is False
        and compiler.get("retention_prior_required") is True
    )
    explicit_family_ready = bool(
        explicit_holdout_ready
        and explicit_retain_count >= required_generatable
        and coverage_ready
        and not coverage_zero
        and coverage_current_count >= required_generatable
        and raw_ready
        and not raw_zero
    )
    combined_family_ready = bool(
        combined_holdout_ready
        and combined_retain_count >= required_generatable
        and alias_retain_count >= 0
        and coverage_ready
        and raw_ready
        and not raw_zero
    )
    checks = {
        "ctspc_v0_frozen": freeze,
        "repair_stack_split_ready": bool(repair.get("repair_stack_split_ready")),
        "compiler_ready": compiler_ready,
        "explicit_holdout_ready": explicit_holdout_ready,
        "wrong_arg_key_alias_holdout_ready": alias_holdout_ready,
        "deterministic_schema_local_holdout_ready": deterministic_holdout_ready,
        "combined_theory_prior_holdout_ready": combined_holdout_ready,
        "stratified_holdout_ready": stratified_holdout_ready,
        "dev_holdout_disjoint": explicit_disjoint,
        "wrong_arg_key_alias_dev_holdout_disjoint": alias_disjoint,
        "deterministic_schema_local_dev_holdout_disjoint": deterministic_disjoint,
        "combined_dev_holdout_disjoint": combined_disjoint,
        "stratified_dev_holdout_disjoint": stratified_disjoint,
        "no_scorer_commands": no_scorer_commands,
        "runtime_manifest_safeguards_passed": safeguards,
        "retention_prior_coverage_audit_ready": coverage_ready,
        "explicit_prior_family_coverage_zero": coverage_zero,
        "raw_bfcl_literal_coverage_audit_ready": raw_ready,
        "explicit_prior_family_raw_prompt_coverage_zero": raw_zero,
        "source_result_availability_audit_ready": availability_audit_ready,
        "source_result_availability_ready": source_result_availability_ready,
        "wrong_arg_key_alias_coverage_audit_ready": alias_coverage_ready,
        "wrong_arg_key_alias_family_coverage_zero": alias_family_coverage_zero,
        "deterministic_schema_local_coverage_audit_ready": deterministic_coverage_ready,
        "deterministic_schema_local_family_coverage_zero": deterministic_family_coverage_zero,
        "explicit_family_scorer_authorization_ready": explicit_family_ready,
        "combined_theory_prior_scorer_authorization_ready": combined_family_ready,
    }
    blockers: list[str] = []
    if not checks["ctspc_v0_frozen"]:
        blockers.append("ctspc_v0_not_frozen")
    if not checks["repair_stack_split_ready"]:
        blockers.append("repair_stack_split_not_ready")
    if not checks["compiler_ready"]:
        blockers.append("compiler_not_ready")
    if not checks["combined_theory_prior_holdout_ready"]:
        blockers.append("combined_theory_prior_holdout_not_ready")
    if not no_scorer_commands:
        blockers.append("scorer_commands_present")
    if not safeguards:
        blockers.append("runtime_manifest_safeguards_failed")
    if not coverage_ready:
        blockers.append("retention_prior_coverage_audit_missing")
    if coverage_zero:
        blockers.append("explicit_prior_family_coverage_zero")
    if raw_zero:
        blockers.append("explicit_prior_family_raw_prompt_coverage_zero")
    if not raw_ready:
        blockers.append("raw_bfcl_literal_coverage_audit_missing")
    if not availability_audit_ready:
        blockers.append("source_result_availability_audit_missing")
    if availability_audit_ready and not source_result_availability_ready:
        blockers.append("source_result_availability_not_ready")
    if not alias_coverage_ready:
        blockers.append("wrong_arg_key_alias_coverage_audit_missing")
    if alias_family_coverage_zero:
        blockers.append("wrong_arg_key_alias_family_coverage_zero")
    if not deterministic_coverage_ready:
        blockers.append("deterministic_schema_local_coverage_audit_missing")
    if deterministic_family_coverage_zero:
        blockers.append("deterministic_schema_local_family_coverage_zero")
    if combined_retain_count < required_generatable:
        blockers.append("combined_demote_candidate_below_35")
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
        checks["source_result_availability_audit_ready"],
        checks["source_result_availability_ready"],
        checks["wrong_arg_key_alias_coverage_audit_ready"],
        checks["deterministic_schema_local_coverage_audit_ready"],
        checks["combined_theory_prior_scorer_authorization_ready"],
    ])
    return {
        "report_scope": "m2_8pre_offline_summary",
        **checks,
        "source_result_literals_prompt_anchored_count": raw_prompt_anchored_count,
        "remaining_gap_to_35_demote_candidates": remaining_gap_to_35,
        "prior_scan_category_coverage": prior_scan_category_coverage,
        "alias_scan_category_coverage": alias_scan_category_coverage,
        "compiler_category_coverage": compiler_category_coverage,
        "deterministic_schema_local_coverage_audit": {key: deterministic_coverage.get(key) for key in [
            "deterministic_schema_local_coverage_audit_ready",
            "deterministic_schema_local_candidate_count",
            "deterministic_schema_local_demote_candidate_count",
            "deterministic_schema_local_family_coverage_zero",
            "rejection_reason_counts",
            "route_recommendation",
            "blockers",
            "candidate_commands",
            "planned_commands",
        ]},
        "wrong_arg_key_alias_coverage_audit": {key: alias_coverage.get(key) for key in [
            "wrong_arg_key_alias_coverage_audit_ready",
            "wrong_arg_key_alias_candidate_count",
            "wrong_arg_key_alias_demote_candidate_count",
            "wrong_arg_key_alias_family_coverage_zero",
            "rejection_reason_counts",
            "route_recommendation",
            "blockers",
            "candidate_commands",
            "planned_commands",
        ]},
        "route_recommendation": route_recommendation,
        "scorer_authorization_ready": scorer_authorization_ready,
        "m2_8pre_offline_passed": scorer_authorization_ready,
        "blockers": blockers,
        "compiler": {key: compiler.get(key) for key in [
            "selected_case_count",
            "candidate_generatable_count",
            "wrong_arg_key_alias_candidate_count",
            "wrong_arg_key_alias_demote_candidate_count",
            "wrong_arg_key_alias_ambiguous_count",
            "wrong_arg_key_alias_value_mutation_count",
            "deterministic_schema_local_candidate_count",
            "deterministic_schema_local_demote_candidate_count",
            "deterministic_schema_local_ambiguous_count",
            "deterministic_schema_local_value_creation_count",
            "combined_retain_eligible_candidate_count",
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
            "retention_prior_rule_families",
            "retention_prior_distribution",
            "wrong_arg_key_alias_retention_prior_distribution",
            "deterministic_schema_local_retention_prior_distribution",
            "combined_retention_prior_distribution",
            "stratified_retention_prior_distribution",
            "retain_eligible_candidate_count",
            "stratified_retain_eligible_candidate_count",
            "theory_prior_explicit_literal_candidate_count",
            "scanner_missed_count",
            "disambiguated_current_context_candidate_count",
            "source_result_only_diagnostic_count",
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
        "source_result_availability_audit": {key: availability.get(key) for key in [
            "source_result_availability_audit_ready",
            "source_result_availability_ready",
            "hard_issue_counts",
            "issue_counts",
            "candidate_commands",
            "planned_commands",
        ]},
        "raw_bfcl_literal_coverage_audit": {key: raw_coverage.get(key) for key in [
            "m28pre_raw_bfcl_literal_coverage_audit_ready",
            "source_result_diagnostic_literal_count",
            "source_result_literals_prompt_anchored_count",
            "source_result_literals_retain_prior_candidate_count",
            "source_result_literals_prompt_coverage_zero",
            "scanner_missed_count",
            "failure_reason_counts",
            "route_recommendation",
            "pivot_to_next_theory_family",
            "candidate_commands",
            "planned_commands",
        ]},
        "dev_manifest": {key: dev.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "authorized_theory_prior_families", "no_next_tool_intervention", "exact_tool_choice"]},
        "holdout_manifest": {key: holdout.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "authorized_theory_prior_families", "no_next_tool_intervention", "exact_tool_choice"]},
        "wrong_arg_key_alias_dev_manifest": {key: alias_dev.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "authorized_theory_prior_families", "no_next_tool_intervention", "exact_tool_choice"]},
        "wrong_arg_key_alias_holdout_manifest": {key: alias_holdout.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "authorized_theory_prior_families", "no_next_tool_intervention", "exact_tool_choice"]},
        "deterministic_schema_local_dev_manifest": {key: deterministic_dev.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "authorized_theory_prior_families", "no_next_tool_intervention", "exact_tool_choice"]},
        "deterministic_schema_local_holdout_manifest": {key: deterministic_holdout.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "authorized_theory_prior_families", "no_next_tool_intervention", "exact_tool_choice"]},
        "combined_dev_manifest": {key: combined_dev.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "authorized_theory_prior_families", "no_next_tool_intervention", "exact_tool_choice"]},
        "combined_holdout_manifest": {key: combined_holdout.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "authorized_theory_prior_families", "no_next_tool_intervention", "exact_tool_choice"]},
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
        f"- Remaining gap to 35 demote candidates: `{report['remaining_gap_to_35_demote_candidates']}`",
        f"- Route recommendation: `{report['route_recommendation']}`",
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
        "source_result_availability_audit_ready",
        "source_result_availability_ready",
        "wrong_arg_key_alias_coverage_audit_ready",
        "wrong_arg_key_alias_family_coverage_zero",
        "deterministic_schema_local_coverage_audit_ready",
        "deterministic_schema_local_family_coverage_zero",
        "no_scorer_commands",
        "runtime_manifest_safeguards_passed",
    ]:
        lines.append(f"| `{key}` | `{report[key]}` |")
    lines.extend(["", "Offline readiness only. No scorer command is emitted by this artifact.", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset-root", type=Path, default=DEFAULT_SUBSET)
    parser.add_argument("--low-risk-root", type=Path, default=DEFAULT_LOW_RISK)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--markdown-output", type=Path, default=MD)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when m2_8pre_offline_passed is false.")
    args = parser.parse_args(argv)
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
            "source_result_availability_audit_ready",
            "source_result_availability_ready",
            "wrong_arg_key_alias_coverage_audit_ready",
            "wrong_arg_key_alias_family_coverage_zero",
            "deterministic_schema_local_coverage_audit_ready",
            "deterministic_schema_local_family_coverage_zero",
            "remaining_gap_to_35_demote_candidates",
            "route_recommendation",
            "no_scorer_commands",
            "blockers",
        ]}, indent=2, sort_keys=True))
    if args.strict and not report.get("m2_8pre_offline_passed"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
