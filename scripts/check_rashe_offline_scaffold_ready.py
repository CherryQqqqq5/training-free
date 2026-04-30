#!/usr/bin/env python3
"""Aggregate fail-closed readiness checker for the RASHE offline scaffold only.

This is not a BFCL performance readiness checker.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_ACTIVE_INDEX = Path("outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json")
DEFAULT_SCOPE_APPROVAL = Path("outputs/artifacts/stage1_bfcl_acceptance/scope_change_approval_rashe.json")
DEFAULT_RUNTIME_AUTH = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_runtime_implementation_authorization.json")
CHECK_COMMANDS = {
    "runtime_skeleton": ["scripts/check_rashe_runtime_skeleton.py", "--compact", "--strict"],
    "step_trace_buffer": ["scripts/check_rashe_step_trace_buffer.py", "--compact", "--strict"],
    "skill_metadata": ["scripts/check_rashe_skill_metadata.py", "--compact", "--strict"],
    "proposer_schema": ["scripts/check_rashe_proposer_schema.py", "--compact", "--strict"],
    "evolution_loop": ["scripts/check_rashe_evolution_loop.py", "--compact", "--strict"],
}
FORBIDDEN_TRUE_FIELDS = (
    "runtime_behavior_authorized",
    "source_collection_authorized",
    "candidate_generation_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def run_checker(script_args: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    cmd = [sys.executable, *script_args]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        return None, f"checker_failed:{script_args[0]}:{result.stdout.strip() or result.stderr.strip()}"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"checker_json_invalid:{script_args[0]}:{exc}"
    if not isinstance(data, dict):
        return None, f"checker_output_not_object:{script_args[0]}"
    return data, None


def _nested_get(data: dict[str, Any], path: tuple[str, ...], default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current


def check(active_index_path: Path = DEFAULT_ACTIVE_INDEX, scope_approval_path: Path = DEFAULT_SCOPE_APPROVAL, runtime_auth_path: Path = DEFAULT_RUNTIME_AUTH) -> dict[str, Any]:
    blockers: list[str] = []
    active = load_json(active_index_path)
    scope = load_json(scope_approval_path)
    runtime_auth = load_json(runtime_auth_path)

    if active.get("active_route") != "retrieval_augmented_skill_harness_evolution":
        blockers.append("active_index_rashe_route_missing")
    if active.get("rashe_route_approved") is not True:
        blockers.append("active_index_rashe_route_not_approved")
    rashe_scaffold = active.get("rashe_offline_scaffold")
    if not isinstance(rashe_scaffold, dict):
        blockers.append("active_index_rashe_offline_scaffold_missing")
        rashe_scaffold = {}
    for key in [
        "runtime_skeleton_passed",
        "step_trace_buffer_offline_passed",
        "skill_metadata_passed",
        "proposer_schema_passed",
        "offline_evolution_loop_passed",
    ]:
        if rashe_scaffold.get(key) is not True and _nested_get(active, ("latest_conclusion", f"rashe_{key}"), None) is not True:
            blockers.append(f"active_index_{key}_not_true")
    for key in FORBIDDEN_TRUE_FIELDS:
        if active.get(key) is True or _nested_get(active, ("claim_readiness", key), False) is True or rashe_scaffold.get(key) is True:
            blockers.append(f"active_index_{key}_true")
    if active.get("formal_bfcl_performance_ready") is True:
        blockers.append("active_index_formal_bfcl_performance_ready_true")
    deterministic_stage1_family_search_exhausted = active.get("deterministic_stage1_family_search_exhausted") is True
    deterministic_paths_zero_yield = active.get("deterministic_argument_structural_and_tool_name_paths_zero_yield") is True
    if not deterministic_stage1_family_search_exhausted:
        blockers.append("active_index_deterministic_stage1_family_search_exhausted_missing")
    if not deterministic_paths_zero_yield:
        blockers.append("active_index_deterministic_argument_paths_zero_yield_missing")
    if active.get("no_bfcl_3pp_evidence_yet") is not True:
        blockers.append("active_index_no_bfcl_3pp_evidence_missing")

    if scope.get("approval_status") != "approved" or scope.get("scope_change_approved") is not True:
        blockers.append("rashe_scope_approval_not_approved")
    if scope.get("scope_change_route") != "retrieval_augmented_skill_harness_evolution":
        blockers.append("rashe_scope_route_invalid")
    for key in FORBIDDEN_TRUE_FIELDS:
        if scope.get(key) is True:
            blockers.append(f"scope_approval_{key}_true")
    if scope.get("active_acceptance_path") is True or scope.get("execution_authorized") is True:
        blockers.append("scope_approval_execution_or_acceptance_path_true")

    if runtime_auth.get("authorization_status") != "approved":
        blockers.append("runtime_authorization_not_approved")
    if runtime_auth.get("runtime_implementation_scope") != "default_disabled_inert_skeleton_only":
        blockers.append("runtime_authorization_scope_invalid")
    for key in [
        "runtime_behavior_authorized",
        "source_collection_authorized",
        "candidate_generation_authorized",
        "candidate_pool_ready",
        "scorer_authorized",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
        "default_enabled",
    ]:
        if runtime_auth.get(key) is True:
            blockers.append(f"runtime_authorization_{key}_true")

    checker_outputs: dict[str, dict[str, Any]] = {}
    for name, command in CHECK_COMMANDS.items():
        data, error = run_checker(command)
        if error:
            blockers.append(error)
            continue
        assert data is not None
        checker_outputs[name] = data
    runtime_skeleton_passed = checker_outputs.get("runtime_skeleton", {}).get("rashe_runtime_skeleton_passed") is True
    step_trace_passed = checker_outputs.get("step_trace_buffer", {}).get("step_trace_buffer_offline_passed") is True
    skill_metadata_passed = checker_outputs.get("skill_metadata", {}).get("rashe_skill_metadata_passed") is True
    proposer_passed = checker_outputs.get("proposer_schema", {}).get("proposer_schema_passed") is True
    evolution_passed = checker_outputs.get("evolution_loop", {}).get("evolution_loop_schema_passed") is True
    for label, passed in [
        ("runtime_skeleton", runtime_skeleton_passed),
        ("step_trace_buffer", step_trace_passed),
        ("skill_metadata", skill_metadata_passed),
        ("proposer_schema", proposer_passed),
        ("evolution_loop", evolution_passed),
    ]:
        if not passed:
            blockers.append(f"{label}_checker_not_passed")
    for name, output in checker_outputs.items():
        for key in ["runtime_behavior_authorized", "candidate_generation_authorized", "scorer_authorized", "performance_evidence"]:
            if output.get(key) is True:
                blockers.append(f"{name}_{key}_true")
        if output.get("provider_call_count", 0) != 0 or output.get("scorer_call_count", 0) != 0 or output.get("source_collection_call_count", 0) != 0:
            blockers.append(f"{name}_call_count_nonzero")

    summary = {
        "report_scope": "rashe_offline_scaffold_readiness_check",
        "not_bfcl_performance_readiness": True,
        "rashe_route_approved": scope.get("approval_status") == "approved" and scope.get("scope_change_approved") is True and active.get("rashe_route_approved") is True,
        "deterministic_stage1_family_search_exhausted": deterministic_stage1_family_search_exhausted,
        "deterministic_argument_structural_and_tool_name_paths_zero_yield": deterministic_paths_zero_yield,
        "rashe_runtime_skeleton_passed": runtime_skeleton_passed,
        "rashe_step_trace_buffer_offline_passed": step_trace_passed,
        "rashe_skill_metadata_passed": skill_metadata_passed,
        "rashe_proposer_schema_passed": proposer_passed,
        "rashe_offline_evolution_loop_passed": evolution_passed,
        "runtime_behavior_authorized": False,
        "source_collection_authorized": False,
        "candidate_generation_authorized": False,
        "candidate_pool_ready": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "bfcl_performance_ready": False,
        "rashe_offline_scaffold_ready": not blockers,
        "blockers": blockers,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-index", type=Path, default=DEFAULT_ACTIVE_INDEX)
    parser.add_argument("--scope-approval", type=Path, default=DEFAULT_SCOPE_APPROVAL)
    parser.add_argument("--runtime-authorization", type=Path, default=DEFAULT_RUNTIME_AUTH)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.active_index, args.scope_approval, args.runtime_authorization)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_offline_scaffold_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
