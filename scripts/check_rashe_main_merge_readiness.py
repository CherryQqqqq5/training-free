#!/usr/bin/env python3
"""Fail-closed main merge readiness checker for the RASHE offline scaffold branch.

This is not BFCL performance readiness.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_REPORT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_main_merge_readiness.json")
DEFAULT_ACTIVE_INDEX = Path("outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json")
EXPECTED_BRANCH = "stage1-bfcl-performance-sprint"
EXPECTED_ROUTE = "retrieval_augmented_skill_harness_evolution"
FORBIDDEN_TRUE_FIELDS = (
    "runtime_behavior_authorized",
    "source_collection_authorized",
    "candidate_generation_authorized",
    "candidate_pool_ready",
    "scorer_authorized",
    "performance_evidence",
    "sota_3pp_claim_ready",
    "huawei_acceptance_ready",
    "bfcl_performance_ready",
    "formal_bfcl_performance_ready",
)
REQUIRED_DOCS = (
    Path("docs/stage1_bfcl_negative_evidence_report.md"),
    Path("docs/stage1_bfcl_scope_change_decision_memo.md"),
    Path("docs/stage1_rashe_approval_packet_review_matrix.md"),
    Path("docs/stage1_rashe_main_merge_readiness.md"),
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def run_json_command(args: list[str]) -> tuple[dict[str, Any] | None, str | None]:
    result = subprocess.run([sys.executable, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        return None, f"command_failed:{args[0]}:{result.stdout.strip() or result.stderr.strip()}"
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return None, f"command_json_invalid:{args[0]}:{exc}"
    if not isinstance(data, dict):
        return None, f"command_output_not_object:{args[0]}"
    return data, None


def run_plain_command(args: list[str]) -> str | None:
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    if result.returncode != 0:
        return f"command_failed:{' '.join(args)}:{result.stdout.strip() or result.stderr.strip()}"
    return None


def git_value(args: list[str]) -> str:
    result = subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return result.stdout.strip()


def nested_forbidden_true(data: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in FORBIDDEN_TRUE_FIELDS and value is True:
                paths.append(path)
            paths.extend(nested_forbidden_true(value, path))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            paths.extend(nested_forbidden_true(value, f"{prefix}[{index}]"))
    return paths


def check(report_path: Path = DEFAULT_REPORT, active_index_path: Path = DEFAULT_ACTIVE_INDEX) -> dict[str, Any]:
    blockers: list[str] = []
    report = load_json(report_path)
    active = load_json(active_index_path)
    branch = git_value(["rev-parse", "--abbrev-ref", "HEAD"])
    head = git_value(["rev-parse", "--short", "HEAD"])

    if branch != EXPECTED_BRANCH:
        blockers.append(f"unexpected_branch:{branch}")
    if report.get("main_merge_claim_scope") != "offline_scaffold_only":
        blockers.append("report_scope_not_offline_scaffold_only")
    if report.get("not_bfcl_performance_readiness") is not True:
        blockers.append("report_not_bfcl_performance_readiness_missing")

    if active.get("active_route") != EXPECTED_ROUTE:
        blockers.append("active_index_route_not_rashe")
    if active.get("rashe_route_approved") is not True:
        blockers.append("active_index_rashe_route_not_approved")
    if active.get("deterministic_stage1_family_search_exhausted") is not True:
        blockers.append("deterministic_negative_evidence_missing")
    if active.get("deterministic_argument_structural_and_tool_name_paths_zero_yield") is not True:
        blockers.append("deterministic_zero_yield_summary_missing")
    if active.get("no_bfcl_3pp_evidence_yet") is not True:
        blockers.append("no_bfcl_3pp_evidence_field_missing")

    for path in REQUIRED_DOCS:
        if not path.exists():
            blockers.append(f"required_doc_missing:{path}")

    for path in nested_forbidden_true(report):
        blockers.append(f"report_forbidden_true:{path}")
    for path in nested_forbidden_true(active):
        if path in FORBIDDEN_TRUE_FIELDS or path.startswith("claim_readiness") or path.startswith("rashe_offline_scaffold"):
            blockers.append(f"active_index_forbidden_true:{path}")

    scaffold, error = run_json_command(["scripts/check_rashe_offline_scaffold_ready.py", "--compact", "--strict"])
    if error:
        blockers.append(error)
        scaffold = {}
    matrix, error = run_json_command(["scripts/check_rashe_approval_packet_review_matrix.py", "--compact", "--strict"])
    if error:
        blockers.append(error)
        matrix = {}
    packets, error = run_json_command(["scripts/check_rashe_approval_packets.py", "--compact", "--strict"])
    if error:
        blockers.append(error)
        packets = {}
    boundary_error = run_plain_command([sys.executable, "scripts/check_artifact_boundary.py"])
    if boundary_error:
        blockers.append(boundary_error)

    rashe_offline_scaffold_ready = bool(scaffold.get("rashe_offline_scaffold_ready") is True)
    approval_matrix_passed = bool(matrix.get("rashe_approval_packet_review_matrix_passed") is True)
    approval_packets_fail_closed = bool(packets.get("rashe_approval_packets_passed") is True)
    artifact_boundary_passed = boundary_error is None
    for label, passed in [
        ("rashe_offline_scaffold_ready", rashe_offline_scaffold_ready),
        ("approval_matrix_passed", approval_matrix_passed),
        ("approval_packets_fail_closed", approval_packets_fail_closed),
        ("artifact_boundary_passed", artifact_boundary_passed),
    ]:
        if not passed:
            blockers.append(f"{label}_false")

    summary = {
        "report_scope": "rashe_main_merge_readiness_check",
        "source_branch": branch,
        "head": head,
        "main_merge_claim_scope": "offline_scaffold_only",
        "not_bfcl_performance_readiness": True,
        "active_evidence_index_route": active.get("active_route"),
        "rashe_offline_scaffold_ready": rashe_offline_scaffold_ready,
        "approval_packet_review_matrix_passed": approval_matrix_passed,
        "approval_packets_fail_closed": approval_packets_fail_closed,
        "artifact_boundary_passed": artifact_boundary_passed,
        "deterministic_negative_evidence_present": active.get("deterministic_stage1_family_search_exhausted") is True and active.get("deterministic_argument_structural_and_tool_name_paths_zero_yield") is True,
        "handoff_docs_present": all(path.exists() for path in REQUIRED_DOCS),
        "runtime_behavior_authorized": False,
        "source_collection_authorized": False,
        "candidate_generation_authorized": False,
        "candidate_pool_ready": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "bfcl_performance_ready": False,
        "rashe_main_merge_ready": not blockers,
        "blockers": blockers,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--active-index", type=Path, default=DEFAULT_ACTIVE_INDEX)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.report, args.active_index)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_main_merge_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
