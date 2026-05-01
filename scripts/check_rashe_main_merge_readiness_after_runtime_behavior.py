#!/usr/bin/env python3
"""Post-runtime-behavior main readiness checker for RASHE.

This is the current gate after L1 runtime behavior approval. The legacy
``check_rashe_main_merge_readiness.py`` remains the pre-runtime/offline-scaffold
gate and is expected to reject approved runtime packets.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

DEFAULT_ACTIVE_INDEX = Path("outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json")
DEFAULT_REPORT = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_main_merge_readiness.json")
EXPECTED_ROUTE = "retrieval_augmented_skill_harness_evolution"
BASE_HANDOFF_COMMIT = "eaafa624"
PRIOR_POST_RUNTIME_CLEANUP_COMMIT = "0ce63ba7d21620a39aa2eae8da8f4128c640e8aa"
DOWNSTREAM_FALSE_FIELDS = (
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
    Path("docs/stage1_rashe_approval_packet_review_matrix.md"),
    Path("docs/stage1_rashe_main_merge_readiness.md"),
    Path("docs/stage1_rashe_runtime_implementation_plan.md"),
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
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


def nested_get(data: dict[str, Any], path: tuple[str, ...], default: Any = None) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return current


def _check_downstream_false(active: dict[str, Any], blockers: list[str]) -> None:
    claim = active.get("claim_readiness") if isinstance(active.get("claim_readiness"), dict) else {}
    for key in DOWNSTREAM_FALSE_FIELDS:
        active_value = active.get(key)
        claim_value = claim.get(key)
        if active_value is True:
            blockers.append(f"active_index_downstream_field_true:{key}")
        if claim_value is True:
            blockers.append(f"claim_readiness_downstream_field_true:{key}")


def validate_active_index(active: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if active.get("active_route") != EXPECTED_ROUTE:
        blockers.append("active_index_route_not_rashe")
    if active.get("branch") != "main":
        blockers.append("active_index_branch_not_main")
    if active.get("main_merge_completed") is not True:
        blockers.append("active_index_main_merge_completed_not_true")
    if active.get("handoff_commit") != BASE_HANDOFF_COMMIT:
        blockers.append("active_index_handoff_commit_invalid")
    if active.get("base_handoff_commit") != BASE_HANDOFF_COMMIT:
        blockers.append("active_index_base_handoff_commit_invalid")
    if active.get("prior_post_runtime_cleanup_commit") != PRIOR_POST_RUNTIME_CLEANUP_COMMIT:
        blockers.append("active_index_prior_post_runtime_cleanup_commit_invalid")
    if active.get("latest_committed_cleanup") != "see git HEAD":
        blockers.append("active_index_latest_cleanup_not_non_self_referential")
    for stale_key in ["current_head", "current_head_note", "artifact_commit"]:
        if stale_key in active:
            blockers.append(f"active_index_self_referential_field_present:{stale_key}")

    if active.get("runtime_behavior_approval_status") != "approved":
        blockers.append("active_index_runtime_behavior_approval_status_not_approved")
    if active.get("runtime_behavior_authorized") is not True:
        blockers.append("active_index_runtime_behavior_authorized_not_true")
    if active.get("runtime_behavior_scope") != "synthetic_default_disabled_only":
        blockers.append("active_index_runtime_behavior_scope_invalid")
    if nested_get(active, ("claim_readiness", "runtime_behavior_approval_status")) != "approved":
        blockers.append("claim_readiness_runtime_behavior_approval_status_not_approved")
    if nested_get(active, ("claim_readiness", "runtime_behavior_authorized")) is not True:
        blockers.append("claim_readiness_runtime_behavior_authorized_not_true")

    scaffold = active.get("rashe_offline_scaffold")
    if not isinstance(scaffold, dict):
        blockers.append("rashe_offline_scaffold_missing")
        scaffold = {}
    if "runtime_behavior_authorized" in scaffold:
        blockers.append("rashe_offline_scaffold_ambiguous_runtime_behavior_authorized_key_present")
    if scaffold.get("runtime_behavior_authorized_by_offline_scaffold") is not False:
        blockers.append("rashe_offline_scaffold_runtime_boundary_missing")
    if scaffold.get("separate_l1_runtime_behavior_packet_authorizes") != "synthetic_default_disabled_only":
        blockers.append("rashe_offline_scaffold_l1_runtime_packet_boundary_invalid")
    for key in [
        "runtime_skeleton_passed",
        "step_trace_buffer_offline_passed",
        "skill_metadata_passed",
        "proposer_schema_passed",
        "offline_evolution_loop_passed",
    ]:
        if scaffold.get(key) is not True:
            blockers.append(f"rashe_offline_scaffold_{key}_not_true")

    _check_downstream_false(active, blockers)
    if active.get("no_bfcl_3pp_evidence_yet") is not True:
        blockers.append("active_index_no_bfcl_3pp_evidence_not_true")
    return blockers


def validate_report(report: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if report.get("report_scope") != "rashe_main_merge_readiness_after_runtime_behavior":
        blockers.append("report_scope_invalid")
    if report.get("main_merge_claim_scope") != "post_runtime_l1_synthetic_default_disabled_only":
        blockers.append("report_claim_scope_invalid")
    if report.get("runtime_behavior_approval_status") != "approved":
        blockers.append("report_runtime_behavior_approval_status_not_approved")
    if report.get("runtime_behavior_scope") != "synthetic_default_disabled_only":
        blockers.append("report_runtime_behavior_scope_invalid")
    if report.get("legacy_pre_runtime_gate") != "scripts/check_rashe_main_merge_readiness.py":
        blockers.append("report_legacy_gate_missing")
    if report.get("current_post_runtime_gate") != "scripts/check_rashe_main_merge_readiness_after_runtime_behavior.py":
        blockers.append("report_current_gate_missing")
    for key in DOWNSTREAM_FALSE_FIELDS:
        if report.get("fail_closed_fields", {}).get(key) is not False:
            blockers.append(f"report_downstream_field_not_false:{key}")
    return blockers


def check(active_index_path: Path = DEFAULT_ACTIVE_INDEX, report_path: Path = DEFAULT_REPORT) -> dict[str, Any]:
    blockers: list[str] = []
    active = load_json(active_index_path)
    report = load_json(report_path)

    blockers.extend(validate_active_index(active))
    blockers.extend(validate_report(report))

    runtime, error = run_json_command(["scripts/check_rashe_runtime_behavior_approved.py", "--compact", "--strict"])
    if error:
        blockers.append(error)
        runtime = {}
    matrix, error = run_json_command(["scripts/check_rashe_approval_packet_review_matrix_after_runtime_behavior.py", "--compact", "--strict"])
    if error:
        blockers.append(error)
        matrix = {}
    boundary_error = run_plain_command([sys.executable, "scripts/check_artifact_boundary.py"])
    if boundary_error:
        blockers.append(boundary_error)

    runtime_approved_passed = bool(runtime.get("rashe_runtime_behavior_approved_passed") is True)
    after_runtime_matrix_passed = bool(matrix.get("rashe_approval_packet_review_matrix_after_runtime_behavior_passed") is True)
    artifact_boundary_passed = boundary_error is None
    for label, passed in [
        ("runtime_behavior_approved_passed", runtime_approved_passed),
        ("after_runtime_matrix_passed", after_runtime_matrix_passed),
        ("artifact_boundary_passed", artifact_boundary_passed),
    ]:
        if not passed:
            blockers.append(f"{label}_false")

    for path in REQUIRED_DOCS:
        if not path.exists():
            blockers.append(f"required_doc_missing:{path}")

    return {
        "report_scope": "rashe_main_merge_readiness_after_runtime_behavior_check",
        "active_index": str(active_index_path),
        "report": str(report_path),
        "target_branch_provenance": active.get("branch"),
        "base_handoff_commit": active.get("base_handoff_commit"),
        "prior_post_runtime_cleanup_commit": active.get("prior_post_runtime_cleanup_commit"),
        "latest_committed_cleanup": active.get("latest_committed_cleanup"),
        "runtime_behavior_approval_status": active.get("runtime_behavior_approval_status"),
        "runtime_behavior_authorized": active.get("runtime_behavior_authorized"),
        "runtime_behavior_scope": active.get("runtime_behavior_scope"),
        "runtime_behavior_approved_passed": runtime_approved_passed,
        "after_runtime_matrix_passed": after_runtime_matrix_passed,
        "artifact_boundary_passed": artifact_boundary_passed,
        "source_collection_authorized": False,
        "candidate_generation_authorized": False,
        "candidate_pool_ready": False,
        "scorer_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "bfcl_performance_ready": False,
        "rashe_main_merge_after_runtime_behavior_ready": not blockers,
        "blockers": blockers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--active-index", type=Path, default=DEFAULT_ACTIVE_INDEX)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.active_index, args.report)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_main_merge_after_runtime_behavior_ready"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
