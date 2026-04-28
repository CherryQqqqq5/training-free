#!/usr/bin/env python3
"""Build a broader observable output-contract preservation coverage audit.

This audit is offline-only. It scans existing compact/raw-pair artifacts to
measure whether the output-contract preservation prior has cross-slice coverage.
It does not call BFCL, models, or scorers and does not authorize scorer runs.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_MEMORY_REPAIR_AUDIT = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_final_answer_repair_audit.json")
DEFAULT_MEMORY_FIX_RESULT = Path("outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_final_answer_fix_smoke_result.json")
DEFAULT_POSTCONDITION_SMOKE_RESULT = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk/postcondition_guided_dev_smoke_result.json")
DEFAULT_MEMORY_RUNTIME_READINESS = Path("outputs/artifacts/phase2/memory_operation_obligation_runtime_smoke_v1/first_pass/memory_operation_runtime_smoke_readiness.json")
DEFAULT_OUT = Path("outputs/artifacts/phase2/output_contract_preservation_v1/observable_output_contract_broader_audit.json")
DEFAULT_MD = Path("outputs/artifacts/phase2/output_contract_preservation_v1/observable_output_contract_broader_audit.md")


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _memory_records(path: Path) -> list[dict[str, Any]]:
    report = _load(path)
    rows = []
    for idx, row in enumerate(report.get("records") or []):
        if not isinstance(row, dict):
            continue
        observable = row.get("output_format_requirement_observable") is True
        preserved = row.get("new_offline_replay_content_preserved") is True
        repair_kinds = row.get("new_offline_replay_repair_kinds") or []
        issue_kinds = row.get("new_offline_replay_issue_kinds") or []
        eligible = observable and preserved and not repair_kinds and not issue_kinds
        rows.append({
            "record_id": row.get("trace_id") or f"memory-final-answer-{idx}",
            "source_artifact": str(path),
            "benchmark_slice": "memory",
            "trace_stage": "offline_replay",
            "has_raw_model_output": True,
            "has_repaired_output": True,
            "raw_structured_payload_present": True,
            "payload_kind": "final_answer",
            "payload_parse_status": "parseable" if eligible else "lossy_or_ambiguous",
            "wrapper_or_container_issue_only": eligible,
            "payload_values_equal_after_repair": eligible,
            "payload_field_set_equal_after_repair": eligible,
            "tool_choice_source": "none",
            "argument_creation_count": 0,
            "payload_value_mutation_count": 0,
            "trajectory_mutation_count": 0,
            "admission_decision": "eligible" if eligible else "blocked",
            "blocked_reason": "none" if eligible else "payload_mutated_or_not_preserved",
            "negative_control_type": "none",
            "expected_activation": eligible,
            "actual_activation": eligible,
            "question_family": row.get("question_family"),
        })
    return rows


def _diagnostic_artifact_record(path: Path, *, benchmark_slice: str, payload_kind: str = "unknown") -> dict[str, Any] | None:
    if not path.exists():
        return None
    return {
        "record_id": path.stem,
        "source_artifact": str(path),
        "benchmark_slice": benchmark_slice,
        "trace_stage": "compact_result",
        "has_raw_model_output": False,
        "has_repaired_output": False,
        "raw_structured_payload_present": False,
        "payload_kind": payload_kind,
        "payload_parse_status": "absent",
        "wrapper_or_container_issue_only": False,
        "payload_values_equal_after_repair": False,
        "payload_field_set_equal_after_repair": False,
        "tool_choice_source": "unknown",
        "argument_creation_count": 0,
        "payload_value_mutation_count": 0,
        "trajectory_mutation_count": 0,
        "admission_decision": "diagnostic",
        "blocked_reason": "insufficient_artifact_pair",
        "negative_control_type": "none",
        "expected_activation": False,
        "actual_activation": False,
    }


def evaluate(
    memory_repair_audit: Path = DEFAULT_MEMORY_REPAIR_AUDIT,
    memory_fix_result: Path = DEFAULT_MEMORY_FIX_RESULT,
    postcondition_smoke_result: Path = DEFAULT_POSTCONDITION_SMOKE_RESULT,
    memory_runtime_readiness: Path = DEFAULT_MEMORY_RUNTIME_READINESS,
) -> dict[str, Any]:
    records = _memory_records(memory_repair_audit)
    diagnostic_inputs = [
        (memory_fix_result, "memory", "final_answer"),
        (postcondition_smoke_result, "multi_turn", "unknown"),
        (memory_runtime_readiness, "memory", "unknown"),
    ]
    for path, benchmark_slice, payload_kind in diagnostic_inputs:
        record = _diagnostic_artifact_record(path, benchmark_slice=benchmark_slice, payload_kind=payload_kind)
        if record:
            records.append(record)

    eligible = [row for row in records if row.get("admission_decision") == "eligible"]
    blocked = [row for row in records if row.get("admission_decision") == "blocked"]
    diagnostic = [row for row in records if row.get("admission_decision") == "diagnostic"]
    eligible_by_payload_kind = Counter(str(row.get("payload_kind") or "unknown") for row in eligible)
    eligible_by_slice = Counter(str(row.get("benchmark_slice") or "unknown") for row in eligible)
    blocked_by_reason = Counter(str(row.get("blocked_reason") or "unknown") for row in blocked + diagnostic)
    artifact_count = len({str(row.get("source_artifact")) for row in records if row.get("source_artifact")})
    raw_pair_count = sum(1 for row in records if row.get("has_raw_model_output") and row.get("has_repaired_output"))
    mutation_count = sum(int(row.get("payload_value_mutation_count") or 0) for row in records)
    arg_creation_count = sum(int(row.get("argument_creation_count") or 0) for row in records)
    trajectory_mutation_count = sum(int(row.get("trajectory_mutation_count") or 0) for row in records)
    negative_control_activation_count = sum(
        1 for row in records
        if row.get("negative_control_type") not in {None, "", "none"} and row.get("actual_activation") is True
    )
    retain_prior_coverage_ready = bool(
        len(eligible_by_payload_kind) >= 2
        or len(eligible_by_slice) >= 2
    ) and negative_control_activation_count == 0 and mutation_count == 0 and arg_creation_count == 0 and trajectory_mutation_count == 0
    blockers = []
    if len(eligible_by_payload_kind) < 2 and len(eligible_by_slice) < 2:
        blockers.append("single_payload_or_slice_coverage_only")
    if negative_control_activation_count:
        blockers.append("negative_control_activation_detected")
    if mutation_count or arg_creation_count or trajectory_mutation_count:
        blockers.append("non_preservation_mutation_detected")
    if raw_pair_count < 1:
        blockers.append("raw_repair_pairs_missing")
    return {
        "report_scope": "observable_output_contract_broader_audit",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "candidate_commands": [],
        "planned_commands": [],
        "artifact_count_scanned": artifact_count,
        "record_count_scanned": len(records),
        "raw_repair_pair_count": raw_pair_count,
        "eligible_preservation_candidate_count": len(eligible),
        "blocked_count": len(blocked),
        "diagnostic_count": len(diagnostic),
        "eligible_by_payload_kind": dict(sorted(eligible_by_payload_kind.items())),
        "eligible_by_benchmark_slice": dict(sorted(eligible_by_slice.items())),
        "blocked_by_reason": dict(sorted(blocked_by_reason.items())),
        "negative_control_activation_count": negative_control_activation_count,
        "payload_value_mutation_count": mutation_count,
        "argument_creation_count": arg_creation_count,
        "rule_generated_tool_choice_count": 0,
        "trajectory_mutation_count": trajectory_mutation_count,
        "retain_prior_coverage_ready": retain_prior_coverage_ready,
        "performance_claim_ready": False,
        "blockers": blockers,
        "records_sample": records[:20],
        "next_required_action": "expand_output_contract_raw_pairs_across_non_memory_slices" if not retain_prior_coverage_ready else "request_strict_output_contract_smoke_review",
    }


def render_markdown(report: dict[str, Any]) -> str:
    return "\n".join([
        "# Observable Output Contract Broader Audit",
        "",
        f"- Retain-prior coverage ready: `{report['retain_prior_coverage_ready']}`",
        f"- Performance claim ready: `{report['performance_claim_ready']}`",
        f"- Artifacts scanned: `{report['artifact_count_scanned']}`",
        f"- Records scanned: `{report['record_count_scanned']}`",
        f"- Raw repair pairs: `{report['raw_repair_pair_count']}`",
        f"- Eligible preservation candidates: `{report['eligible_preservation_candidate_count']}`",
        f"- Eligible by payload kind: `{report['eligible_by_payload_kind']}`",
        f"- Eligible by benchmark slice: `{report['eligible_by_benchmark_slice']}`",
        f"- Blocked by reason: `{report['blocked_by_reason']}`",
        f"- Negative-control activations: `{report['negative_control_activation_count']}`",
        f"- Mutation counts (payload/arg/trajectory): `{report['payload_value_mutation_count']}` / `{report['argument_creation_count']}` / `{report['trajectory_mutation_count']}`",
        f"- Blockers: `{report['blockers']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "Offline diagnostic only. It does not authorize BFCL/model/scorer runs.",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--memory-repair-audit", type=Path, default=DEFAULT_MEMORY_REPAIR_AUDIT)
    parser.add_argument("--memory-fix-result", type=Path, default=DEFAULT_MEMORY_FIX_RESULT)
    parser.add_argument("--postcondition-smoke-result", type=Path, default=DEFAULT_POSTCONDITION_SMOKE_RESULT)
    parser.add_argument("--memory-runtime-readiness", type=Path, default=DEFAULT_MEMORY_RUNTIME_READINESS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.memory_repair_audit, args.memory_fix_result, args.postcondition_smoke_result, args.memory_runtime_readiness)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        print(json.dumps({
            "retain_prior_coverage_ready": report["retain_prior_coverage_ready"],
            "performance_claim_ready": report["performance_claim_ready"],
            "raw_repair_pair_count": report["raw_repair_pair_count"],
            "eligible_preservation_candidate_count": report["eligible_preservation_candidate_count"],
            "eligible_by_payload_kind": report["eligible_by_payload_kind"],
            "eligible_by_benchmark_slice": report["eligible_by_benchmark_slice"],
            "negative_control_activation_count": report["negative_control_activation_count"],
            "blockers": report["blockers"],
            "next_required_action": report["next_required_action"],
        }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
