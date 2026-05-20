#!/usr/bin/env python3
"""
check_abhe_v0_per_case_scorer_slicer_rerun_manifest_ready
==========================================================

Fail-closed gate for the G6a per-case scorer slicer rerun manifest.

Exit 0 ONLY when ALL of:
  - manifest present
  - schema/version match
  - all attestation booleans (provider_calls_made, bfcl_*_called,
    scorer_called, executor_actually_executed, etc.) are False
  - signed_approval_packet_sha256 matches the file on disk
  - source_matrix_sha256 matches the file on disk
  - target_case_count == 24
  - expected_subrun_count == 72
  - expected_post_slicing_unique_scorer_unit_count_for_target == 24
  - current_pre_slicing_unique_scorer_unit_count_for_target == 1
  - executor_ready_to_proceed is True
  - caps_satisfied_by_estimate is True
  - blockers list is empty

This is intentionally NOT in the merge gate. It is invoked by the
future executor (G6b) before consuming the manifest.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_rerun_manifest.json"

EXPECTED_KIND = "abhe_v0_per_case_scorer_slicer_rerun_manifest"
EXPECTED_SCHEMA = "abhe_v0_per_case_scorer_slicer_rerun_manifest_v0"

ATTESTATION_MUST_FALSE = [
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called", "runtime_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
    "executor_actually_executed",
]

ATTESTATION_MUST_TRUE = ["bounded_dev_smoke_only", "raw_material_absent"]


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def check(strict: bool) -> dict:
    blockers = []
    if not ARTIFACT.exists():
        return {
            "abhe_v0_per_case_scorer_slicer_rerun_manifest_ready": False,
            "blockers": ["manifest_missing"],
            "report_scope": "abhe_v0_per_case_scorer_slicer_rerun_manifest_ready_check",
        }
    m = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    if m.get("artifact_kind") != EXPECTED_KIND:
        blockers.append("artifact_kind_invalid")
    if m.get("schema_version") != EXPECTED_SCHEMA:
        blockers.append("schema_version_invalid")
    for k in ATTESTATION_MUST_FALSE:
        if m.get(k) is not False:
            blockers.append(f"{k}_not_false")
    for k in ATTESTATION_MUST_TRUE:
        if m.get(k) is not True:
            blockers.append(f"{k}_not_true")

    # sha256 reverification
    pkt_path = m.get("signed_approval_packet_path")
    if pkt_path:
        full = REPO_ROOT / pkt_path
        if full.exists():
            actual = _sha256(full)
            if actual != m.get("signed_approval_packet_sha256"):
                blockers.append("signed_approval_packet_sha256_mismatch")
        else:
            blockers.append("signed_approval_packet_path_missing_on_disk")
    src_path = m.get("source_matrix_path")
    if src_path:
        full = REPO_ROOT / src_path
        if full.exists():
            actual = _sha256(full)
            if actual != m.get("source_matrix_sha256"):
                blockers.append("source_matrix_sha256_mismatch")
        else:
            blockers.append("source_matrix_path_missing_on_disk")

    if m.get("target_case_count") != 24:
        blockers.append(f"target_case_count_not_24:{m.get('target_case_count')}")
    if m.get("expected_subrun_count") != 72:
        blockers.append(f"expected_subrun_count_not_72:{m.get('expected_subrun_count')}")
    if m.get("expected_post_slicing_unique_scorer_unit_count_for_target") != 24:
        blockers.append("expected_post_slicing_unique_scorer_unit_count_for_target_not_24")
    if m.get("current_pre_slicing_unique_scorer_unit_count_for_target") != 1:
        blockers.append(
            f"current_pre_slicing_unique_scorer_unit_count_for_target_not_1:"
            f"{m.get('current_pre_slicing_unique_scorer_unit_count_for_target')}"
        )
    if m.get("executor_ready_to_proceed") is not True:
        blockers.append("executor_ready_to_proceed_not_true")
    if m.get("caps_satisfied_by_estimate") is not True:
        blockers.append("caps_satisfied_by_estimate_not_true")

    subruns = m.get("subruns") or []
    if len(subruns) != 72:
        blockers.append(f"subruns_count_not_72:{len(subruns)}")
    arms_seen = sorted({s.get("arm") for s in subruns})
    if arms_seen != ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]:
        blockers.append(f"arms_mismatch:{arms_seen}")

    if m.get("blockers"):
        blockers.append("builder_reported_blockers:" + ",".join(map(str, m["blockers"])))

    ready = len(blockers) == 0
    return {
        "abhe_v0_per_case_scorer_slicer_rerun_manifest_ready": ready,
        "target_category": m.get("target_category"),
        "target_case_count": m.get("target_case_count"),
        "expected_subrun_count": m.get("expected_subrun_count"),
        "expected_post_slicing_unique_scorer_unit_count_for_target":
            m.get("expected_post_slicing_unique_scorer_unit_count_for_target"),
        "current_pre_slicing_unique_scorer_unit_count_for_target":
            m.get("current_pre_slicing_unique_scorer_unit_count_for_target"),
        "executor_ready_to_proceed": m.get("executor_ready_to_proceed"),
        "executor_actually_executed": m.get("executor_actually_executed"),
        "caps_satisfied_by_estimate": m.get("caps_satisfied_by_estimate"),
        "estimated_total_tokens": m.get("estimated_total_tokens"),
        "estimated_total_wall_clock_s": m.get("estimated_total_wall_clock_s"),
        "blockers": blockers,
        "report_scope": "abhe_v0_per_case_scorer_slicer_rerun_manifest_ready_check",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args(argv)
    r = check(strict=args.strict)
    print(json.dumps(r, ensure_ascii=False))
    return 0 if r["abhe_v0_per_case_scorer_slicer_rerun_manifest_ready"] else 1


if __name__ == "__main__":
    sys.exit(main())
