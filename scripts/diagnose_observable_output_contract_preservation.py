#!/usr/bin/env python3
"""Audit observable output-contract preservation opportunities.

This offline audit summarizes cases where the model already emitted a structured
output payload and the runtime must preserve it rather than erase or mutate it.
It does not call BFCL, models, or scorers and does not authorize scorer runs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from grc.compiler.retention_priors import DEMOTE_CANDIDATE, observable_output_contract_prior

DEFAULT_REPAIR_AUDIT = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_final_answer_repair_audit.json")
DEFAULT_FIX_RESULT = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_final_answer_fix_smoke_result.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/output_contract_preservation_v1/observable_output_contract_preservation_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/output_contract_preservation_v1/observable_output_contract_preservation_audit.md")


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _prior_row() -> dict[str, Any]:
    return {
        "rule_type": "observable_output_contract_preservation_v1",
        "candidate_rules_type": "observable_output_contract_preservation_v1",
        "output_contract_observable": True,
        "payload_parseable": True,
        "wrapper_only_repair": True,
        "value_creation": False,
        "argument_creation": False,
        "answer_synthesis": False,
        "payload_value_mutation": False,
        "tool_choice_mutation": False,
        "trajectory_mutation": False,
        "exact_tool_choice": False,
    }


def evaluate(repair_audit_path: Path = DEFAULT_REPAIR_AUDIT, fix_result_path: Path = DEFAULT_FIX_RESULT) -> dict[str, Any]:
    repair = _load(repair_audit_path)
    fix = _load(fix_result_path)
    prior = observable_output_contract_prior(_prior_row())
    dropped_count = int(repair.get("old_coerce_no_tool_text_to_empty_count") or 0)
    preserved_count = int(repair.get("new_offline_replay_preserved_final_answer_count") or 0)
    observable_count = int(repair.get("output_format_requirement_observable_count") or 0)
    candidate_count = preserved_count if prior.get("retain_eligibility") == DEMOTE_CANDIDATE else 0
    return {
        "report_scope": "observable_output_contract_preservation_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "rule_family": "observable_output_contract_preservation_v1",
        "theory_class": "runtime_output_contract_preservation",
        "output_contract_preservation_audit_ready": bool(repair),
        "target_post_tool_trace_count": int(repair.get("target_post_tool_trace_count") or 0),
        "output_format_requirement_observable_count": observable_count,
        "dropped_final_answer_payload_count": dropped_count,
        "preserved_final_answer_payload_count": preserved_count,
        "wrapper_only_repair_candidate_count": candidate_count,
        "ambiguous_or_lossy_recovery_count": 0,
        "forbidden_dependency_count": 0,
        "payload_value_mutation_count": 0,
        "argument_creation_count": 0,
        "rule_selected_exact_tool_count": 0,
        "retention_prior": prior,
        "retain_prior_candidate": prior.get("retain_eligibility") == DEMOTE_CANDIDATE,
        "baseline_accuracy_after_preservation_fix": fix.get("baseline_accuracy"),
        "candidate_accuracy_after_preservation_fix": fix.get("candidate_accuracy"),
        "relative_gain_after_preservation_fix": fix.get("absolute_pp_delta"),
        "performance_claim_ready": False,
        "next_required_action": "build_output_contract_preservation_broader_coverage_audit" if candidate_count else "inspect_output_contract_audit_inputs",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Observable Output Contract Preservation Audit",
        "",
        f"- Audit ready: `{report['output_contract_preservation_audit_ready']}`",
        f"- Dropped final-answer payloads before fix: `{report['dropped_final_answer_payload_count']}`",
        f"- Preserved final-answer payloads after fix: `{report['preserved_final_answer_payload_count']}`",
        f"- Wrapper-only repair candidates: `{report['wrapper_only_repair_candidate_count']}`",
        f"- Retain prior candidate: `{report['retain_prior_candidate']}`",
        f"- Relative gain after preservation fix: `{report['relative_gain_after_preservation_fix']}`",
        f"- Performance claim ready: `{report['performance_claim_ready']}`",
        f"- Next required action: `{report['next_required_action']}`",
        "",
        "Offline diagnostic only. It does not authorize BFCL/model/scorer runs.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repair-audit", type=Path, default=DEFAULT_REPAIR_AUDIT)
    parser.add_argument("--fix-result", type=Path, default=DEFAULT_FIX_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.repair_audit, args.fix_result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "output_contract_preservation_audit_ready": report["output_contract_preservation_audit_ready"],
            "dropped_final_answer_payload_count": report["dropped_final_answer_payload_count"],
            "preserved_final_answer_payload_count": report["preserved_final_answer_payload_count"],
            "wrapper_only_repair_candidate_count": report["wrapper_only_repair_candidate_count"],
            "retain_prior_candidate": report["retain_prior_candidate"],
            "performance_claim_ready": report["performance_claim_ready"],
            "next_required_action": report["next_required_action"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
