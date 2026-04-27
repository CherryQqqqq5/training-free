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
    no_scorer_commands = _no_commands(compiler, dev, holdout, strat_dev, strat_holdout)
    safeguards = bool(
        compiler.get("ctspc_v0_action_rules_enabled") is False
        and compiler.get("ctspc_v0_file_path_multi_turn_enabled") is False
        and compiler.get("repair_stack_default") == "disabled"
        and compiler.get("candidate_rules_type") == "explicit_required_arg_literal_completion"
        and compiler.get("no_next_tool_intervention") is True
        and compiler.get("exact_tool_choice") is False
        and compiler.get("retention_prior_required") is True
        and int(compiler.get("retain_eligible_candidate_count") or 0) > 0
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
    }
    scorer_authorization_ready = all([
        checks["ctspc_v0_frozen"],
        checks["repair_stack_split_ready"],
        checks["compiler_ready"],
        checks["no_scorer_commands"],
        checks["runtime_manifest_safeguards_passed"],
        checks["explicit_holdout_ready"] or checks["stratified_holdout_ready"],
    ])
    return {
        "report_scope": "m2_8pre_offline_summary",
        **checks,
        "scorer_authorization_ready": scorer_authorization_ready,
        "m2_8pre_offline_passed": scorer_authorization_ready,
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
        ]},
        "dev_manifest": {key: dev.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "no_next_tool_intervention", "exact_tool_choice"]},
        "holdout_manifest": {key: holdout.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "no_next_tool_intervention", "exact_tool_choice"]},
        "stratified_dev_manifest": {key: strat_dev.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "no_next_tool_intervention", "exact_tool_choice"]},
        "stratified_holdout_manifest": {key: strat_holdout.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands", "candidate_rules_type", "no_next_tool_intervention", "exact_tool_choice"]},
        "diagnostic": {
            "offline_readiness_only": True,
            "does_not_authorize_scorer_without_separate_request": True,
            "no_bfcl_or_model_call": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# M2.8-pre Offline Summary", "", f"- Passed: `{report['m2_8pre_offline_passed']}`", f"- Scorer authorization ready: `{report['scorer_authorization_ready']}`", "", "| Check | Passed |", "| --- | ---: |"]
    for key in ["ctspc_v0_frozen", "repair_stack_split_ready", "compiler_ready", "explicit_holdout_ready", "stratified_holdout_ready", "no_scorer_commands", "runtime_manifest_safeguards_passed"]:
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
        print(json.dumps({key: report.get(key) for key in ["m2_8pre_offline_passed", "scorer_authorization_ready", "ctspc_v0_frozen", "repair_stack_split_ready", "compiler_ready", "explicit_holdout_ready", "stratified_holdout_ready", "no_scorer_commands"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
