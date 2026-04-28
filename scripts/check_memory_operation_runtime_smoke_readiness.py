#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml

from grc.runtime.engine import RuleEngine
import scripts.check_memory_operation_dry_run_policy as dry_check
import scripts.simulate_memory_operation_activation as activation_sim

DEFAULT_POLICY_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_dry_run_v1/first_pass")
DEFAULT_RUNTIME_RULES_DIR = Path("outputs/artifacts/phase2/memory_operation_obligation_runtime_smoke_v1/first_pass")
DEFAULT_OUT = DEFAULT_RUNTIME_RULES_DIR / "memory_operation_runtime_smoke_readiness.json"
DEFAULT_MD = DEFAULT_RUNTIME_RULES_DIR / "memory_operation_runtime_smoke_readiness.md"

FORBIDDEN_RUNTIME_TEXT = re.compile(
    r"(trace_relative_path|source_audit_record|support_record_hash|case_id|run_name|gold|scorer|bfcl_result|raw_prompt|raw_output|request_original|repairs\.jsonl|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
FORBIDDEN_MUTATION_TEXT = re.compile(r"\b(clear|remove|delete|add|replace|update|append|write|insert|set)\b", re.IGNORECASE)
ALLOWED_PROVIDER = "novacode"
POLICY_UNIT_ID = "memory_first_pass_retrieve_soft_v1"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_yaml_files(path: Path) -> list[tuple[Path, Any, str]]:
    rows: list[tuple[Path, Any, str]] = []
    if not path.exists():
        return rows
    for item in sorted(path.glob("*.yaml")):
        text = item.read_text(encoding="utf-8")
        try:
            data = yaml.safe_load(text) or {}
        except Exception:
            data = None
        rows.append((item, data, text))
    return rows


def _runtime_rule_summaries(rules: list[Any]) -> list[dict[str, Any]]:
    summaries = []
    for rule in rules:
        action = getattr(rule, "action", None)
        decision_policy = getattr(action, "decision_policy", None) if action is not None else None
        if hasattr(decision_policy, "model_dump"):
            policy = decision_policy.model_dump(mode="json", exclude_none=True)
        elif hasattr(decision_policy, "dict"):
            policy = decision_policy.dict(exclude_none=True)
        elif isinstance(decision_policy, dict):
            policy = decision_policy
        else:
            policy = {}
        summaries.append({
            "rule_id": getattr(rule, "rule_id", None),
            "enabled": bool(getattr(rule, "enabled", False)),
            "priority": getattr(rule, "priority", None),
            "policy_family": policy.get("policy_family") or policy.get("family"),
            "recommended_tools": policy.get("recommended_tools") or [],
            "candidate_commands": policy.get("candidate_commands") or [],
            "planned_commands": policy.get("planned_commands") or [],
        })
    return summaries


def evaluate(
    policy_dir: Path = DEFAULT_POLICY_DIR,
    runtime_rules_dir: Path = DEFAULT_RUNTIME_RULES_DIR,
    *,
    max_cases: int = 6,
    provider: str = ALLOWED_PROVIDER,
) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    dry_report = dry_check.evaluate(policy_dir)
    activation_report = activation_sim.evaluate()
    if dry_report.get("dry_run_policy_boundary_check_passed") is not True:
        failures.append({"check": "dry_run_policy_boundary_check_passed", "detail": dry_report.get("first_failure")})
    if activation_report.get("activation_simulation_passed") is not True:
        failures.append({"check": "activation_simulation_passed"})
    if provider != ALLOWED_PROVIDER:
        failures.append({"check": "provider_is_novacode", "provider": provider})
    if max_cases < 1 or max_cases > 8:
        failures.append({"check": "small_smoke_case_limit", "max_cases": max_cases})

    yaml_rows = _read_yaml_files(runtime_rules_dir)
    if not runtime_rules_dir.exists():
        failures.append({"check": "runtime_rules_dir_exists", "path": str(runtime_rules_dir)})
    if not yaml_rows:
        failures.append({"check": "runtime_rule_yaml_present", "path": str(runtime_rules_dir)})

    policy_unit_only_files = []
    forbidden_text_files = []
    forbidden_mutation_files = []
    command_files = []
    for path, data, text in yaml_rows:
        if isinstance(data, dict) and "policy_units" in data and "rules" not in data and "rule_id" not in data:
            policy_unit_only_files.append(str(path))
        if FORBIDDEN_RUNTIME_TEXT.search(text):
            forbidden_text_files.append(str(path))
        if FORBIDDEN_MUTATION_TEXT.search(text):
            forbidden_mutation_files.append(str(path))
        if isinstance(data, dict) and (data.get("candidate_commands") or data.get("planned_commands")):
            command_files.append(str(path))
    if policy_unit_only_files:
        failures.append({"check": "runtime_rules_not_policy_unit_metadata", "files": policy_unit_only_files})
    if forbidden_text_files:
        failures.append({"check": "runtime_rule_forbidden_text", "files": forbidden_text_files})
    if forbidden_mutation_files:
        failures.append({"check": "runtime_rule_forbidden_memory_mutation_text", "files": forbidden_mutation_files})
    if command_files:
        failures.append({"check": "runtime_rule_has_commands", "files": command_files})

    loaded_rules = []
    runtime_load_error = None
    if runtime_rules_dir.exists():
        try:
            loaded_rules = RuleEngine(runtime_rules_dir).rules
        except Exception as exc:  # pragma: no cover - defensive for malformed future rules
            runtime_load_error = str(exc)
            failures.append({"check": "runtime_rules_loadable_by_rule_engine", "error": runtime_load_error})
    if not loaded_rules:
        failures.append({"check": "runtime_adapter_rules_loaded", "loaded_rule_count": 0})

    summaries = _runtime_rule_summaries(loaded_rules)
    memory_rules = [row for row in summaries if str(row.get("rule_id") or "").startswith(POLICY_UNIT_ID)]
    if loaded_rules and not memory_rules:
        failures.append({"check": "memory_first_pass_runtime_rule_present", "loaded_rule_ids": [row.get("rule_id") for row in summaries]})
    for row in summaries:
        if row.get("candidate_commands") or row.get("planned_commands"):
            failures.append({"check": "runtime_rule_policy_has_commands", "rule_id": row.get("rule_id")})

    adapter_ready = not failures
    return {
        "report_scope": "memory_operation_runtime_smoke_readiness",
        "offline_only": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "provider_required": ALLOWED_PROVIDER,
        "provider": provider,
        "max_cases": max_cases,
        "policy_dir": str(policy_dir),
        "runtime_rules_dir": str(runtime_rules_dir),
        "dry_run_policy_boundary_check_passed": dry_report.get("dry_run_policy_boundary_check_passed") is True,
        "activation_simulation_passed": activation_report.get("activation_simulation_passed") is True,
        "activation_count": int(activation_report.get("activation_count") or 0),
        "negative_control_activation_count": int(activation_report.get("negative_control_activation_count") or 0),
        "argument_creation_count": int(activation_report.get("argument_creation_count") or 0),
        "memory_runtime_adapter_ready": adapter_ready,
        "memory_dev_smoke_ready": adapter_ready,
        "loaded_runtime_rule_count": len(loaded_rules),
        "loaded_memory_runtime_rule_count": len(memory_rules),
        "runtime_rule_summaries": summaries,
        "failure_count": len(failures),
        "first_failure": failures[0] if failures else None,
        "failures": failures[:50],
        "candidate_commands": [],
        "planned_commands": [],
        "next_required_action": "implement_runtime_rule_adapter_before_memory_dev_smoke" if not adapter_ready else "request_separate_memory_only_dev_smoke_approval",
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Memory Operation Runtime Smoke Readiness",
        "",
        "- Memory runtime adapter ready: `{}`".format(report["memory_runtime_adapter_ready"]),
        "- Memory dev smoke ready: `{}`".format(report["memory_dev_smoke_ready"]),
        "- Loaded runtime rules: `{}`".format(report["loaded_runtime_rule_count"]),
        "- Loaded memory runtime rules: `{}`".format(report["loaded_memory_runtime_rule_count"]),
        "- Dry-run boundary passed: `{}`".format(report["dry_run_policy_boundary_check_passed"]),
        "- Activation simulation passed: `{}`".format(report["activation_simulation_passed"]),
        "- Activation count: `{}`".format(report["activation_count"]),
        "- Negative-control activation count: `{}`".format(report["negative_control_activation_count"]),
        "- Argument creation count: `{}`".format(report["argument_creation_count"]),
        "- First failure: `{}`".format(report["first_failure"]),
        "- Next required action: `{}`".format(report["next_required_action"]),
        "",
        "This is an offline readiness check. It does not run BFCL/model/scorer and does not authorize smoke execution.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-dir", type=Path, default=DEFAULT_POLICY_DIR)
    parser.add_argument("--runtime-rules-dir", type=Path, default=DEFAULT_RUNTIME_RULES_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_MD)
    parser.add_argument("--max-cases", type=int, default=6)
    parser.add_argument("--provider", default=ALLOWED_PROVIDER)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = evaluate(args.policy_dir, args.runtime_rules_dir, max_cases=args.max_cases, provider=args.provider)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.markdown_output.write_text(render_markdown(report), encoding="utf-8")
    if args.compact:
        keys = [
            "memory_runtime_adapter_ready",
            "memory_dev_smoke_ready",
            "loaded_runtime_rule_count",
            "loaded_memory_runtime_rule_count",
            "dry_run_policy_boundary_check_passed",
            "activation_simulation_passed",
            "activation_count",
            "negative_control_activation_count",
            "argument_creation_count",
            "failure_count",
            "first_failure",
            "next_required_action",
            "candidate_commands",
            "planned_commands",
        ]
        print(json.dumps({key: report.get(key) for key in keys}, indent=2, sort_keys=True))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if args.strict and not report["memory_dev_smoke_ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
