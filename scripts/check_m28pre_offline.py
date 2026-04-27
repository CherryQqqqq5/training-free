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


def evaluate(subset_root: Path = DEFAULT_SUBSET, low_risk_root: Path = DEFAULT_LOW_RISK) -> dict[str, Any]:
    status = _j(subset_root / "m27ae_ctspc_v0_status.json", {}) or {}
    repair = _j(subset_root / "repair_stack_contribution.json", {}) or {}
    compiler = _j(low_risk_root / "compiler_summary.json", {}) or {}
    dev = _j(low_risk_root / "explicit_required_arg_literal_dev20_manifest.json", {}) or {}
    holdout = _j(low_risk_root / "explicit_required_arg_literal_holdout20_manifest.json", {}) or {}
    freeze = bool(
        status.get("ctspc_v0_frozen")
        and status.get("scorer_default") == "off"
        and status.get("retain") == 0
        and status.get("dev_rerun_authorized") is False
        and status.get("holdout_authorized") is False
    )
    dev_ids = set(str(x) for x in dev.get("selected_case_ids") or [])
    holdout_ids = set(str(x) for x in holdout.get("selected_case_ids") or [])
    checks = {
        "ctspc_v0_frozen": freeze,
        "repair_stack_split_ready": bool(repair.get("repair_stack_split_ready")),
        "explicit_required_arg_literal_compiler_passed": bool(compiler.get("m28pre_explicit_required_arg_literal_compiler_passed")),
        "explicit_required_arg_literal_holdout_ready": bool(compiler.get("m28pre_explicit_required_arg_literal_holdout_ready")),
        "dev_holdout_disjoint": not (dev_ids & holdout_ids),
        "no_scorer_commands": not (compiler.get("planned_commands") or compiler.get("candidate_commands") or dev.get("planned_commands") or holdout.get("planned_commands")),
        "ctspc_v0_action_rules_disabled": compiler.get("ctspc_v0_action_rules_enabled") is False,
    }
    return {
        "report_scope": "m2_8pre_offline_summary",
        **checks,
        "m2_8pre_offline_passed": all(checks.values()),
        "compiler": {key: compiler.get(key) for key in ["selected_case_count", "candidate_generatable_count", "ambiguous_literal_count", "blockers"]},
        "dev_manifest": {key: dev.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands"]},
        "holdout_manifest": {key: holdout.get(key) for key in ["manifest_name", "selected_case_count", "selected_case_ids", "planned_commands"]},
        "diagnostic": {
            "offline_readiness_only": True,
            "does_not_authorize_scorer": True,
            "no_bfcl_or_model_call": True,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# M2.8-pre Offline Summary", "", f"- Passed: `{report['m2_8pre_offline_passed']}`", "", "| Check | Passed |", "| --- | ---: |"]
    for key in ["ctspc_v0_frozen", "repair_stack_split_ready", "explicit_required_arg_literal_compiler_passed", "explicit_required_arg_literal_holdout_ready", "dev_holdout_disjoint", "no_scorer_commands", "ctspc_v0_action_rules_disabled"]:
        lines.append(f"| `{key}` | `{report[key]}` |")
    lines.extend(["", "Offline readiness only. No scorer is authorized by this artifact.", ""])
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
        print(json.dumps({key: report.get(key) for key in ["m2_8pre_offline_passed", "ctspc_v0_frozen", "repair_stack_split_ready", "explicit_required_arg_literal_compiler_passed", "explicit_required_arg_literal_holdout_ready", "no_scorer_commands"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
