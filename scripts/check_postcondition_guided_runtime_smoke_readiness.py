#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from grc.runtime.engine import RuleEngine

import scripts.audit_postcondition_guided_dry_run_activation as activation_audit
import scripts.build_postcondition_guided_runtime_smoke_adapter as adapter
import scripts.check_postcondition_guided_dry_run_policy as dry_check

DEFAULT_POLICY_DIR = Path("outputs/artifacts/phase2/postcondition_guided_policy_dry_run_v1/approved_low_risk")
DEFAULT_RUNTIME_DIR = Path("outputs/artifacts/phase2/postcondition_guided_policy_runtime_smoke_v1/approved_low_risk")
DEFAULT_OUT = DEFAULT_RUNTIME_DIR / "postcondition_guided_runtime_smoke_readiness.json"
DEFAULT_MD = DEFAULT_RUNTIME_DIR / "postcondition_guided_runtime_smoke_readiness.md"


def _request(user_text: str, tools: list[str], tool_content: Any | None = None) -> dict[str, Any]:
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_text}]
    if tool_content is not None:
        messages.extend([
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "find", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": json.dumps(tool_content)},
        ])
    return {
        "model": "demo-model",
        "messages": messages,
        "tools": [
            {"type": "function", "function": {"name": name, "parameters": {"type": "object", "properties": {"file_name": {"type": "string"}, "pattern": {"type": "string"}}, "required": []}}}
            for name in tools
        ],
    }


def _plan(runtime_dir: Path, request_json: dict[str, Any]) -> dict[str, Any]:
    engine = RuleEngine(str(runtime_dir), runtime_policy={"enable_required_next_tool_choice": True})
    patched, patches = engine.apply_request(request_json)
    return dict(getattr(patches, "next_tool_plan", {}) or {})


def evaluate(policy_dir: Path = DEFAULT_POLICY_DIR, runtime_dir: Path = DEFAULT_RUNTIME_DIR) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    dry_report = dry_check.evaluate(policy_dir)
    activation_report = activation_audit.evaluate(policy_dir)
    compile_report = adapter.evaluate(policy_dir)
    if dry_report.get("dry_run_policy_boundary_check_passed") is not True:
        failures.append({"check": "dry_run_policy_boundary_check_passed", "detail": dry_report.get("first_failure")})
    if compile_report.get("runtime_adapter_compile_ready") is not True:
        failures.append({"check": "runtime_adapter_compile_ready", "detail": compile_report.get("first_failure")})
    rule_path = runtime_dir / "rule.yaml"
    if not rule_path.exists():
        failures.append({"check": "runtime_rule_yaml_present"})
    read_plan = search_plan = final_plan = {}
    if not failures:
        read_plan = _plan(runtime_dir, _request("Read the contents of report.txt.", ["cat"], {"matches": ["report.txt"]}))
        search_plan = _plan(runtime_dir, _request("Find the TODO marker in the files.", ["grep", "find"], {"files": ["a.txt"]}))
        final_plan = _plan(runtime_dir, _request("Summarize the prior result.", ["cat"], {"content": "done"}))
        if read_plan.get("activated") is not True or read_plan.get("recommended_tools") != ["cat"]:
            failures.append({"check": "read_content_plan_activates", "plan": read_plan})
        if search_plan.get("activated") is not True or search_plan.get("recommended_tools") != ["grep", "find"]:
            failures.append({"check": "search_or_find_plan_activates", "plan": search_plan})
        if final_plan.get("activated") is True:
            failures.append({"check": "final_answer_goal_negative_control", "plan": final_plan})
    smoke_ready = not failures
    return {
        "report_scope": "postcondition_guided_runtime_smoke_readiness",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "postcondition_guided_runtime_smoke_ready": smoke_ready,
        "dry_run_policy_boundary_check_passed": dry_report.get("dry_run_policy_boundary_check_passed"),
        "runtime_adapter_compile_ready": compile_report.get("runtime_adapter_compile_ready"),
        "runtime_rule_count": compile_report.get("runtime_rule_count"),
        "approved_record_replay_activation_count": activation_report.get("approved_record_replay_activation_count"),
        "negative_control_activation_count": activation_report.get("negative_control_activation_count"),
        "synthetic_read_content_activated": bool(read_plan.get("activated")),
        "synthetic_search_or_find_activated": bool(search_plan.get("activated")),
        "synthetic_final_answer_negative_control_activated": bool(final_plan.get("activated")),
        "exact_tool_choice": False,
        "argument_creation_count": 0,
        "candidate_commands": [],
        "planned_commands": [],
        "failure_count": len(failures),
        "first_failure": failures[0] if failures else None,
        "failures": failures[:50],
        "next_required_action": "request_explicit_small_paired_smoke_approval" if smoke_ready else "fix_postcondition_runtime_smoke_readiness",
    }


def write_outputs(report: dict[str, Any], out: Path = DEFAULT_OUT, md_out: Path = DEFAULT_MD) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md = [
        "# Postcondition-Guided Runtime Smoke Readiness",
        "",
        f"- Ready: `{report['postcondition_guided_runtime_smoke_ready']}`",
        f"- Runtime adapter compile ready: `{report['runtime_adapter_compile_ready']}`",
        f"- Runtime rule count: `{report['runtime_rule_count']}`",
        f"- Synthetic read activation: `{report['synthetic_read_content_activated']}`",
        f"- Synthetic search activation: `{report['synthetic_search_or_find_activated']}`",
        f"- Final-answer negative control activated: `{report['synthetic_final_answer_negative_control_activated']}`",
        f"- First failure: `{report['first_failure']}`",
        "",
        "Offline readiness only. This does not call BFCL/model/scorer and does not authorize holdout/full BFCL.",
        "",
    ]
    md_out.write_text("\n".join(md), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-dir", type=Path, default=DEFAULT_POLICY_DIR)
    parser.add_argument("--runtime-dir", type=Path, default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.policy_dir, args.runtime_dir)
    write_outputs(report, args.output, args.markdown_output)
    if args.compact:
        keys = [
            "postcondition_guided_runtime_smoke_ready", "runtime_adapter_compile_ready",
            "runtime_rule_count", "synthetic_read_content_activated", "synthetic_search_or_find_activated",
            "synthetic_final_answer_negative_control_activated", "does_not_authorize_scorer",
            "candidate_commands", "planned_commands", "failure_count", "first_failure", "next_required_action",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    return 0 if report["postcondition_guided_runtime_smoke_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
