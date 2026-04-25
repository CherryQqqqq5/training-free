#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

DEFAULT_ROOT = Path("outputs/artifacts/bfcl_ctspc_subset30_v1")
DEFAULT_RULE_PATH = Path("outputs/phase2_subset/bfcl_ctspc_subset30_v1/candidate_rules/rule.yaml")
DEFAULT_RUNTIME_CONFIG = Path("configs/runtime_bfcl_structured.yaml")
DEFAULT_OUTPUT = DEFAULT_ROOT / "m27o_candidate_quality.json"
DEFAULT_MD_OUTPUT = DEFAULT_ROOT / "m27o_candidate_quality.md"
HIGH_RISK_THRESHOLD = 5


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _iter_rule_candidates(rule_doc: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    rows: list[tuple[str, dict[str, Any]]] = []
    for rule in rule_doc.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        rule_id = str(rule.get("rule_id") or "unknown")
        policy = ((rule.get("action") or {}).get("decision_policy") or {}) if isinstance(rule.get("action"), dict) else {}
        for candidate in policy.get("action_candidates") or []:
            if isinstance(candidate, dict):
                rows.append((rule_id, candidate))
    return rows


def _looks_like_file(value: str) -> bool:
    basename = value.rstrip("/").split("/")[-1]
    return bool(basename) and "." in basename and not value.endswith("/")


def _candidate_arg_value(candidate: dict[str, Any]) -> str:
    args = candidate.get("args") if isinstance(candidate.get("args"), dict) else {}
    for value in args.values():
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _file_dir_type_mismatch(candidate: dict[str, Any]) -> str | None:
    tool = str(candidate.get("tool") or "")
    value = _candidate_arg_value(candidate)
    if tool == "mkdir" and value and _looks_like_file(value):
        return "mkdir_file_literal"
    if tool == "cat" and value and not _looks_like_file(value):
        return "cat_directory_or_unknown_literal"
    if tool == "touch" and value and not _looks_like_file(value):
        return "touch_without_file_literal"
    return None


def _candidate_risk_score(candidate: dict[str, Any]) -> int:
    try:
        score = int(candidate.get("trajectory_risk_score"))
    except (TypeError, ValueError):
        score = 0
    if not isinstance(candidate.get("postcondition"), dict) or not candidate.get("postcondition"):
        score = max(score, 8)
    return score


def _candidate_intervention_mode(candidate: dict[str, Any]) -> str:
    mode = str(candidate.get("intervention_mode") or "").strip()
    return mode if mode in {"record_only", "weak_guidance", "guidance"} else "record_only"


def _classify_case(row: dict[str, Any]) -> str:
    if not row.get("policy_plan_activated"):
        return "not_activated"
    if row.get("case_fixed"):
        return "fixed"
    if row.get("case_regressed"):
        return "regressed"
    if row.get("recommended_tool_match") is True and row.get("raw_normalized_arg_match") is True and not row.get("candidate_success"):
        return "local_tool_arg_match_but_trajectory_fail"
    if row.get("recommended_tool_match") is not True:
        return "tool_mismatch"
    if row.get("raw_normalized_arg_match") is not True:
        return "arg_realization_mismatch"
    if row.get("candidate_success"):
        return "candidate_success"
    return "continuation_or_final_answer"


def evaluate_candidate_quality(
    root: Path = DEFAULT_ROOT,
    *,
    rule_path: Path = DEFAULT_RULE_PATH,
    runtime_config: Path = DEFAULT_RUNTIME_CONFIG,
) -> dict[str, Any]:
    rows = _read_jsonl(root / "subset_case_report.jsonl")
    rule_doc = _load_yaml(rule_path)
    runtime = _load_yaml(runtime_config)
    policy = runtime.get("runtime_policy") if isinstance(runtime.get("runtime_policy"), dict) else runtime
    exact_mode = str((policy or {}).get("exact_next_tool_choice_mode") or "")

    candidates = _iter_rule_candidates(rule_doc)
    missing_postcondition: list[dict[str, Any]] = []
    type_mismatch: list[dict[str, Any]] = []
    high_risk_intervention: list[dict[str, Any]] = []
    rule_stats: dict[str, Counter[str]] = {}
    for rule_id, candidate in candidates:
        stats = rule_stats.setdefault(rule_id, Counter())
        stats["action_candidate_count"] += 1
        tool = str(candidate.get("tool") or "")
        postcondition = candidate.get("postcondition") if isinstance(candidate.get("postcondition"), dict) else {}
        if not postcondition:
            stats["postcondition_missing_count"] += 1
            missing_postcondition.append({"rule_id": rule_id, "tool": tool, "args": candidate.get("args") or {}})
        mismatch = _file_dir_type_mismatch(candidate)
        if mismatch:
            stats["file_dir_type_mismatch_count"] += 1
            type_mismatch.append({"rule_id": rule_id, "tool": tool, "args": candidate.get("args") or {}, "reason": mismatch})
        risk_score = _candidate_risk_score(candidate)
        mode = _candidate_intervention_mode(candidate)
        if mode == "guidance" and risk_score >= HIGH_RISK_THRESHOLD:
            stats["high_risk_candidate_intervention_count"] += 1
            high_risk_intervention.append(
                {
                    "rule_id": rule_id,
                    "tool": tool,
                    "args": candidate.get("args") or {},
                    "trajectory_risk_score": risk_score,
                    "trajectory_risk_flags": candidate.get("trajectory_risk_flags") or ["postcondition_missing"],
                }
            )

    case_distribution = Counter(_classify_case(row) for row in rows)
    activated_rows = [row for row in rows if row.get("policy_plan_activated")]
    trajectory_sensitive_exact_forcing_count = 0 if exact_mode == "guidance_only" else None
    postcondition_missing_count = len(missing_postcondition)
    file_dir_type_mismatch_count = len(type_mismatch)
    high_risk_candidate_intervention_count = len(high_risk_intervention)
    gate_passed = (
        postcondition_missing_count == 0
        and file_dir_type_mismatch_count == 0
        and high_risk_candidate_intervention_count == 0
        and trajectory_sensitive_exact_forcing_count == 0
        and exact_mode == "guidance_only"
    )
    failed: list[str] = []
    if postcondition_missing_count:
        failed.append("postcondition_missing_count")
    if file_dir_type_mismatch_count:
        failed.append("file_dir_type_mismatch_count")
    if high_risk_candidate_intervention_count:
        failed.append("high_risk_candidate_intervention_count")
    if trajectory_sensitive_exact_forcing_count != 0:
        failed.append("trajectory_sensitive_exact_forcing_count")
    if exact_mode != "guidance_only":
        failed.append("guidance_only_mode")

    return {
        "root": str(root),
        "rule_path": str(rule_path),
        "runtime_config": str(runtime_config),
        "candidate_quality_gate_passed": gate_passed,
        "postcondition_missing_count": postcondition_missing_count,
        "file_dir_type_mismatch_count": file_dir_type_mismatch_count,
        "high_risk_candidate_intervention_count": high_risk_candidate_intervention_count,
        "trajectory_sensitive_exact_forcing_count": trajectory_sensitive_exact_forcing_count,
        "exact_next_tool_choice_mode": exact_mode,
        "activated_case_count": len(activated_rows),
        "case_failure_layer_distribution": dict(sorted(case_distribution.items())),
        "rule_level_diagnostics": [
            {"rule_id": rule_id, **dict(counter)} for rule_id, counter in sorted(rule_stats.items())
        ],
        "sample_postcondition_missing": missing_postcondition[:10],
        "sample_file_dir_type_mismatch": type_mismatch[:10],
        "sample_high_risk_candidate_intervention": high_risk_intervention[:10],
        "diagnostic": {
            "checker_scope": "m2_7o_candidate_quality_no_bfcl_no_model_call",
            "first_failed_criterion": failed[0] if failed else None,
            "failed_criteria": failed,
            "do_not_rerun_m2_7f_until_passed": not gate_passed,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    diag = report.get("diagnostic") or {}
    lines = [
        "# M2.7o Candidate Quality",
        "",
        f"- candidate_quality_gate_passed: `{report.get('candidate_quality_gate_passed')}`",
        f"- first_failed_criterion: `{diag.get('first_failed_criterion')}`",
        f"- exact_next_tool_choice_mode: `{report.get('exact_next_tool_choice_mode')}`",
        f"- postcondition_missing_count: `{report.get('postcondition_missing_count')}`",
        f"- file_dir_type_mismatch_count: `{report.get('file_dir_type_mismatch_count')}`",
        f"- high_risk_candidate_intervention_count: `{report.get('high_risk_candidate_intervention_count')}`",
        f"- trajectory_sensitive_exact_forcing_count: `{report.get('trajectory_sensitive_exact_forcing_count')}`",
        "",
        "## Case Failure Layers",
    ]
    for key, value in sorted((report.get("case_failure_layer_distribution") or {}).items()):
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    lines.append("## Rule Diagnostics")
    for row in report.get("rule_level_diagnostics") or []:
        lines.append(
            "- " + str(row.get("rule_id"))
            + f": candidates=`{row.get('action_candidate_count', 0)}`, "
            + f"missing_postcondition=`{row.get('postcondition_missing_count', 0)}`, "
            + f"type_mismatch=`{row.get('file_dir_type_mismatch_count', 0)}`, "
            + f"high_risk_intervention=`{row.get('high_risk_candidate_intervention_count', 0)}`"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Check M2.7o trajectory-aware candidate quality without running BFCL.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--rule-path", type=Path, default=DEFAULT_RULE_PATH)
    parser.add_argument("--runtime-config", type=Path, default=DEFAULT_RUNTIME_CONFIG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD_OUTPUT)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()

    report = evaluate_candidate_quality(args.root, rule_path=args.rule_path, runtime_config=args.runtime_config)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        keys = [
            "candidate_quality_gate_passed",
            "postcondition_missing_count",
            "file_dir_type_mismatch_count",
            "high_risk_candidate_intervention_count",
            "trajectory_sensitive_exact_forcing_count",
            "exact_next_tool_choice_mode",
            "activated_case_count",
            "diagnostic",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report.get("candidate_quality_gate_passed") else 1)


if __name__ == "__main__":
    main()
