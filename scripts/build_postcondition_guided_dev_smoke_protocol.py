#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from grc.runtime.engine import RuleEngine

import scripts.check_postcondition_guided_runtime_smoke_readiness as readiness

DEFAULT_CANDIDATE_MANIFEST = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/postcondition_guided_policy_candidate_manifest.json")
DEFAULT_AUDIT = Path("outputs/artifacts/phase2/policy_conversion_opportunity_v1/policy_conversion_opportunity_audit.json")
DEFAULT_RUNTIME_DIR = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk")
DEFAULT_OUT_DIR = DEFAULT_RUNTIME_DIR
ALLOWED_GAPS = {"read_content", "search_or_find"}
MAX_SMOKE_CASES = 9
PROVIDER_REQUIRED = "novacode"


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_hash(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _selected_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in manifest.get("candidate_records") or []:
        if not isinstance(row, dict):
            continue
        if row.get("low_risk_dry_run_review_eligible") is not True:
            continue
        if row.get("ambiguity_flags"):
            continue
        records.append(row)
    return records


def _trace_root(audit: dict[str, Any]) -> Path:
    root = audit.get("trace_root") or "outputs/phase2_validation/required_next_tool_choice_v1"
    return Path(str(root))


def _runtime_plan(runtime_dir: Path, request_payload: dict[str, Any]) -> dict[str, Any]:
    engine = RuleEngine(str(runtime_dir), runtime_policy={"enable_required_next_tool_choice": True})
    _patched, patches = engine.apply_request(request_payload)
    return dict(getattr(patches, "next_tool_plan", {}) or {})


def _case_record(row: dict[str, Any], trace_root: Path, runtime_dir: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    rel = Path(str(row.get("trace_relative_path") or row.get("source_audit_record_pointer") or ""))
    trace_path = trace_root / rel
    failure = None
    if not rel.as_posix() or not trace_path.exists():
        failure = {"check": "source_trace_present", "candidate_id": row.get("candidate_id"), "trace_relative_path": rel.as_posix()}
    tools = [str(tool) for tool in row.get("recommended_tools") or []]
    case = {
        "candidate_id": row.get("candidate_id"),
        "run_name": row.get("run_name"),
        "trace_relative_path": rel.as_posix(),
        "trace_sha256": _sha256_file(trace_path),
        "trace_request_sha256": None,
        "postcondition_gap": row.get("postcondition_gap"),
        "recommended_tools": tools,
        "failure_labels": row.get("failure_labels") or [],
        "request_predicates": row.get("request_predicates") or [],
        "intervention_strength": row.get("intervention_strength"),
        "exact_tool_choice": row.get("exact_tool_choice"),
        "argument_creation": False,
        "source_runtime_enabled": row.get("runtime_enabled"),
        "runtime_plan_activated": False,
        "runtime_plan_selected_tool": None,
        "runtime_plan_blocked_reason": None,
    }
    if trace_path.exists():
        try:
            trace = _load_json(trace_path)
            request_payload = trace.get("request") if isinstance(trace, dict) else None
            if request_payload is not None:
                case["trace_request_sha256"] = _stable_hash(request_payload)
                plan = _runtime_plan(runtime_dir, request_payload)
                case["runtime_plan_activated"] = bool(plan.get("activated"))
                case["runtime_plan_selected_tool"] = plan.get("selected_tool")
                case["runtime_plan_blocked_reason"] = plan.get("blocked_reason")
        except Exception as exc:  # pragma: no cover - corrupt local artifact guard
            failure = {"check": "source_trace_json_readable", "candidate_id": row.get("candidate_id"), "error": str(exc)}
    return case, failure


def evaluate(
    candidate_manifest_path: Path = DEFAULT_CANDIDATE_MANIFEST,
    audit_path: Path = DEFAULT_AUDIT,
    runtime_dir: Path = DEFAULT_RUNTIME_DIR,
    max_cases: int = MAX_SMOKE_CASES,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    manifest = _load_json(candidate_manifest_path)
    audit = _load_json(audit_path)
    ready = readiness.evaluate(runtime_dir=runtime_dir)
    if ready.get("postcondition_guided_runtime_smoke_ready") is not True:
        failures.append({"check": "postcondition_guided_runtime_smoke_ready", "detail": ready.get("first_failure")})
    if manifest.get("candidate_commands"):
        failures.append({"check": "manifest_has_no_candidate_commands"})
    if manifest.get("planned_commands"):
        failures.append({"check": "manifest_has_no_planned_commands"})

    selected = _selected_records(manifest)[:max_cases]
    if len(selected) != max_cases:
        failures.append({"check": "selected_low_risk_case_count", "actual": len(selected), "expected": max_cases})
    trace_root = _trace_root(audit)
    cases: list[dict[str, Any]] = []
    for row in selected:
        gap = str(row.get("postcondition_gap") or "")
        if gap not in ALLOWED_GAPS:
            failures.append({"check": "allowed_postcondition_gap", "candidate_id": row.get("candidate_id"), "gap": gap})
        if row.get("exact_tool_choice") is not False:
            failures.append({"check": "exact_tool_choice_false", "candidate_id": row.get("candidate_id")})
        if row.get("intervention_strength") != "guidance_only":
            failures.append({"check": "guidance_only_intervention", "candidate_id": row.get("candidate_id")})
        case, failure = _case_record(row, trace_root, runtime_dir)
        cases.append(case)
        if failure:
            failures.append(failure)

    capability_distribution: dict[str, int] = {}
    for case in cases:
        gap = str(case.get("postcondition_gap") or "")
        capability_distribution[gap] = capability_distribution.get(gap, 0) + 1

    runtime_replay_activation_count = sum(int(bool(case.get("runtime_plan_activated"))) for case in cases)
    runtime_replay_inactive_cases = [
        {
            "candidate_id": case.get("candidate_id"),
            "postcondition_gap": case.get("postcondition_gap"),
            "blocked_reason": case.get("runtime_plan_blocked_reason"),
        }
        for case in cases
        if not case.get("runtime_plan_activated")
    ]
    if runtime_replay_activation_count < 1:
        failures.append({"check": "runtime_replay_activation_count_positive", "actual": runtime_replay_activation_count})

    selected_case_hash = _stable_hash([
        {
            "candidate_id": case.get("candidate_id"),
            "trace_relative_path": case.get("trace_relative_path"),
            "postcondition_gap": case.get("postcondition_gap"),
            "recommended_tools": case.get("recommended_tools"),
            "trace_request_sha256": case.get("trace_request_sha256"),
            "runtime_plan_activated": case.get("runtime_plan_activated"),
            "runtime_plan_selected_tool": case.get("runtime_plan_selected_tool"),
        }
        for case in cases
    ])
    protocol_ready = not failures and bool(cases)
    return {
        "report_scope": "postcondition_guided_dev_smoke_protocol",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "smoke_protocol_ready_for_review": protocol_ready,
        "provider_required": PROVIDER_REQUIRED,
        "max_cases": max_cases,
        "selected_case_count": len(cases),
        "selected_case_list_hash": selected_case_hash,
        "trace_root": str(trace_root),
        "runtime_rule_path": str(runtime_dir / "rule.yaml"),
        "runtime_rule_sha256": _sha256_file(runtime_dir / "rule.yaml"),
        "capability_distribution": capability_distribution,
        "runtime_replay_activation_count": runtime_replay_activation_count,
        "runtime_replay_inactive_case_count": len(runtime_replay_inactive_cases),
        "runtime_replay_inactive_cases": runtime_replay_inactive_cases,
        "selected_smoke_cases": cases,
        "postcondition_guided_runtime_smoke_ready": ready.get("postcondition_guided_runtime_smoke_ready"),
        "synthetic_final_answer_negative_control_activated": ready.get("synthetic_final_answer_negative_control_activated"),
        "synthetic_no_prior_tool_output_negative_control_activated": ready.get("synthetic_no_prior_tool_output_negative_control_activated"),
        "synthetic_missing_capability_negative_control_activated": ready.get("synthetic_missing_capability_negative_control_activated"),
        "hard_pins": ["provider_required", "selected_case_list_hash", "runtime_rule_sha256"],
        "positive_lane_case_count": runtime_replay_activation_count,
        "diagnostic_inactive_case_count": len(runtime_replay_inactive_cases),
        "control_lane": {
            "synthetic_final_answer_negative_control_activated": ready.get("synthetic_final_answer_negative_control_activated"),
            "synthetic_no_prior_tool_output_negative_control_activated": ready.get("synthetic_no_prior_tool_output_negative_control_activated"),
            "synthetic_missing_capability_negative_control_activated": ready.get("synthetic_missing_capability_negative_control_activated"),
            "required_control_activation_count": 0,
        },
        "exact_tool_choice": False,
        "argument_creation_count": 0,
        "candidate_commands": [],
        "planned_commands": [],
        "baseline_command": None,
        "candidate_command": None,
        "smoke_execution_requires_explicit_approval": True,
        "forbidden_scope": ["holdout", "100-case", "full_bfcl", "retain_claim", "sota_3pp_claim"],
        "pre_registered_primary_metrics": [
            "candidate_valid",
            "baseline_valid",
            "case_fixed_count",
            "case_regressed_count",
            "net_case_gain",
            "absolute_pp_delta",
            "activated_case_count",
        ],
        "pre_registered_stop_loss": {
            "case_regressed_count_eq_0": True,
            "net_case_gain_gt_0": True,
            "candidate_valid": True,
            "baseline_valid": True,
            "no_final_answer_stripping_regression": True,
            "control_activation_count_eq_0": True,
            "exact_tool_choice_count_eq_0": True,
            "argument_creation_count_eq_0": True,
        },
        "invalidity_clauses": [
            "selected_case_hash_changed",
            "runtime_rule_hash_changed",
            "provider_not_novacode",
            "candidate_or_planned_command_embedded",
            "exact_tool_choice_enabled",
            "argument_creation_detected",
            "activation_without_prior_tool_output",
            "activation_when_capability_missing",
            "activation_when_postcondition_already_satisfied",
            "no_last_message_or_final_answer_stripping_regression",
            "activation_outside_read_content_or_search_or_find",
        ],
        "pre_registered_diagnostic_metrics": [
            "activation_by_capability",
            "negative_control_activation_count",
            "candidate_tool_call_after_gap_count",
            "candidate_observation_acquired_count",
            "candidate_unnecessary_tool_count",
            "candidate_loop_or_extra_tool_count",
        ],
        "failure_count": len(failures),
        "first_failure": failures[0] if failures else None,
        "failures": failures[:50],
        "next_required_action": "request_explicit_postcondition_guided_paired_smoke_execution_approval" if protocol_ready else "fix_postcondition_guided_smoke_protocol_inputs",
    }


def write_outputs(report: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "postcondition_guided_dev_smoke_protocol.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Postcondition-Guided Dev Smoke Protocol",
        "",
        f"- Ready for review: `{report['smoke_protocol_ready_for_review']}`",
        f"- Provider required: `{report['provider_required']}`",
        f"- Selected case count: `{report['selected_case_count']}`",
        f"- Capability distribution: `{report['capability_distribution']}`",
        f"- Selected case list hash: `{report['selected_case_list_hash']}`",
        f"- Runtime rule hash: `{report['runtime_rule_sha256']}`",
        f"- Candidate commands: `{report['candidate_commands']}`",
        f"- Planned commands: `{report['planned_commands']}`",
        f"- Does not authorize scorer: `{report['does_not_authorize_scorer']}`",
        f"- Positive lane case count: `{report['positive_lane_case_count']}`",
        f"- Diagnostic inactive case count: `{report['diagnostic_inactive_case_count']}`",
        f"- Control lane: `{report['control_lane']}`",
        f"- Hard pins: `{report['hard_pins']}`",
        f"- First failure: `{report['first_failure']}`",
        f"- Next action: `{report['next_required_action']}`",
        "",
        "This protocol freezes a tiny postcondition-guided paired smoke design. It does not run BFCL/model/scorer.",
        "The smoke is limited to low-risk read/search capability guidance and cannot support retain, holdout, 100-case, or SOTA claims.",
        "",
    ]
    (out_dir / "postcondition_guided_dev_smoke_protocol.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-manifest", type=Path, default=DEFAULT_CANDIDATE_MANIFEST)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--max-cases", type=int, default=MAX_SMOKE_CASES)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.candidate_manifest, args.audit, args.runtime_dir, args.max_cases)
    write_outputs(report, args.output_dir)
    if args.compact:
        keys = [
            "smoke_protocol_ready_for_review",
            "provider_required",
            "selected_case_count",
            "selected_case_list_hash",
            "runtime_rule_sha256",
            "capability_distribution",
            "runtime_replay_activation_count",
            "runtime_replay_inactive_case_count",
            "hard_pins",
            "control_lane",
            "candidate_commands",
            "planned_commands",
            "does_not_authorize_scorer",
            "failure_count",
            "first_failure",
            "next_required_action",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["smoke_protocol_ready_for_review"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
