#!/usr/bin/env python3
"""
build_abhe_v0_per_case_scorer_slicer_rerun_manifest
====================================================

G6a — planning-only manifest builder for the P1.5b per-case scorer
slicer rerun. NO PROVIDER CALL. NO BFCL CALL. NO SCORER CALL.

What this builder does:
  1. Reads the signed P1.5b approval packet (must pass strict checker)
  2. Reads the source per_selected_id_matrix
  3. Filters to 24 multi_turn_miss_param selected rows
  4. For each (case_stable_hash x arm) = 24 x 3 = 72 sub-runs, emits a
     planning record describing what the single-case evaluator
     invocation WOULD look like (the slicing).
  5. Estimates token + wall-clock costs against caps in signed packet.
  6. Emits a compact manifest under outputs/artifacts/stage1_bfcl_acceptance/.

What this builder does NOT do:
  - It does NOT call any provider
  - It does NOT call BFCL generate/evaluate
  - It does NOT call any scorer
  - It does NOT touch holdout / full-suite / archive
  - It does NOT commit raw prompts / gold / expected / argument_values

The intent: produce a manifest that a future executor (G6b) can consume
to deterministically run the slicer with cap enforcement.

LITERATURE / RATIONALE
----------------------
Per-case scorer invocation is the honest fix for C1 (CLAUDE_RESUME): the
BFCL scorer in batch mode aggregates 24 multi_turn_miss_param cases into
a single scorer_unit, making per-case pass labels inheritance-only. By
invoking the scorer once per case (single-case manifest input), each
case produces its own scorer_unit, and the P1 score-output contract
becomes satisfiable.

See:
  outputs/artifacts/stage1_bfcl_acceptance/
    abhe_v0_p1_5b_per_case_scorer_slicer_approval_packet_draft.md
    abhe_v0_per_case_scorer_slicer_approval_packet.json  (SIGNED, G5)
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SIGNED_PACKET = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_approval_packet.json"
SOURCE_MATRIX = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_per_selected_id_matrix.json"
OUTPUT_PATH = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_rerun_manifest.json"

EXPECTED_TARGET = "multi_turn_miss_param"
EXPECTED_ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]
EXPECTED_TARGET_CASE_COUNT = 24

# Token estimate per (case, arm): a multi_turn_miss_param case typically
# has 3-8 turns with ~2-5k tokens per turn. Conservative average ~20k.
DEFAULT_TOKEN_ESTIMATE_PER_SUBRUN = 25000
# Wall-clock estimate per sub-run: ~30s serial; assume serial for planning
DEFAULT_WALL_CLOCK_S_PER_SUBRUN = 30

ALLOWED_TOP_KEYS = {
    "artifact_kind", "schema_version", "run_scope", "bounded_dev_smoke_only",
    "raw_material_absent",
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called", "runtime_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
    "signed_approval_packet_path", "signed_approval_packet_sha256",
    "source_matrix_path", "source_matrix_sha256",
    "target_category", "approved_arms",
    "target_case_count", "expected_subrun_count",
    "expected_post_slicing_unique_scorer_unit_count_for_target",
    "expected_post_slicing_compact_to_scorer_unit_factor",
    "current_pre_slicing_unique_scorer_unit_count_for_target",
    "subruns",
    "estimated_total_tokens",
    "estimated_total_wall_clock_s",
    "caps_from_signed_packet",
    "caps_satisfied_by_estimate",
    "executor_ready_to_proceed",
    "executor_actually_executed",
    "blockers",
}

ALLOWED_SUBRUN_KEYS = {
    "subrun_index", "arm", "case_stable_hash", "case_identifier_hash",
    "dataset_raw_id_hash", "selected_index", "selected_index_within_dataset_raw_id",
    "scorer_invocation_mode",
    "estimated_tokens", "estimated_wall_clock_s",
}

ALLOWED_CAPS_KEYS = {
    "cost_latency_cap_token_budget", "cost_latency_cap_wall_clock_s",
    "regression_cap_error_class_delta_max_cases",
    "cost_amplification_cap_factor", "provider_504_rate_cap_pct",
}

FORBIDDEN_SUBSTRINGS = ("prompt", "gold", "expected_argument",
                       "argument_value", "raw_response", "raw_payload", "scorer_diff")
ATTESTATION_ALLOWLIST_KEYS = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "expected_post_slicing_unique_scorer_unit_count_for_target",
    "expected_post_slicing_compact_to_scorer_unit_factor",
    "expected_subrun_count",
}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_forbidden(obj, path="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ATTESTATION_ALLOWLIST_KEYS:
                _scan_forbidden(v, f"{path}.{k}")
                continue
            kl = str(k).lower()
            for bad in FORBIDDEN_SUBSTRINGS:
                if bad in kl:
                    raise ValueError(f"forbidden_field_in_key:{path}.{k}")
            _scan_forbidden(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            _scan_forbidden(x, f"{path}[{i}]")


def _load_signed_packet() -> Dict[str, Any]:
    """Read the signed packet AND invoke the strict checker. Refuse to
    build the manifest unless strict checker exits 0."""
    from scripts.check_abhe_v0_per_case_scorer_slicer_approval_packet import check
    r = check(SIGNED_PACKET, strict=True)
    if not r.get("approval_packet_passed"):
        raise ValueError(
            "signed_packet_strict_check_failed:" + ",".join(r.get("blockers") or [])
        )
    if r.get("approval_status") != "approved":
        raise ValueError("signed_packet_not_in_approved_state")
    if r.get("authorized") is not True:
        raise ValueError("signed_packet_not_authorized")
    return json.loads(SIGNED_PACKET.read_text(encoding="utf-8"))


def _filter_target_rows(matrix: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = matrix.get("selected_id_rows") or []
    target = [r for r in rows if r.get("bfcl_category") == EXPECTED_TARGET]
    return target


def _make_subrun(idx: int, row: Dict[str, Any], arm: str) -> Dict[str, Any]:
    return {
        "subrun_index": idx,
        "arm": arm,
        "case_stable_hash": row.get("case_stable_hash"),
        "case_identifier_hash": row.get("case_identifier_hash"),
        "dataset_raw_id_hash": row.get("dataset_raw_id_hash"),
        "selected_index": row.get("selected_index"),
        "selected_index_within_dataset_raw_id": row.get("selected_index_within_dataset_raw_id"),
        "scorer_invocation_mode": "single_case_manifest_input",
        "estimated_tokens": DEFAULT_TOKEN_ESTIMATE_PER_SUBRUN,
        "estimated_wall_clock_s": DEFAULT_WALL_CLOCK_S_PER_SUBRUN,
    }


def build(strict: bool) -> Dict[str, Any]:
    packet = _load_signed_packet()
    sig = packet.get("signature_block") or {}
    caps = {
        "cost_latency_cap_token_budget": sig.get("cost_latency_cap_token_budget"),
        "cost_latency_cap_wall_clock_s": sig.get("cost_latency_cap_wall_clock_s"),
        "regression_cap_error_class_delta_max_cases": sig.get("regression_cap_error_class_delta_max_cases"),
        "cost_amplification_cap_factor": sig.get("cost_amplification_cap_factor"),
        "provider_504_rate_cap_pct": sig.get("provider_504_rate_cap_pct"),
    }
    matrix = json.loads(SOURCE_MATRIX.read_text(encoding="utf-8"))
    target_rows = _filter_target_rows(matrix)
    blockers: List[str] = []

    if len(target_rows) != EXPECTED_TARGET_CASE_COUNT:
        blockers.append(
            f"target_row_count_mismatch:{len(target_rows)}_expected_{EXPECTED_TARGET_CASE_COUNT}"
        )

    # Dedupe by case_stable_hash for safety; per the source matrix this is already 1:1
    seen_hashes = set()
    target_rows_dedup = []
    for r in target_rows:
        h = r.get("case_stable_hash")
        if h not in seen_hashes:
            seen_hashes.add(h)
            target_rows_dedup.append(r)

    pre_slicing_unique_scorer_units = len({r.get("scorer_unit_hash") for r in target_rows})

    subruns: List[Dict[str, Any]] = []
    idx = 0
    for r in target_rows_dedup:
        for arm in EXPECTED_ARMS:
            subruns.append(_make_subrun(idx, r, arm))
            idx += 1

    expected_subrun_count = EXPECTED_TARGET_CASE_COUNT * len(EXPECTED_ARMS)
    if len(subruns) != expected_subrun_count:
        blockers.append(f"subrun_count_mismatch:{len(subruns)}_expected_{expected_subrun_count}")

    estimated_total_tokens = sum(s["estimated_tokens"] for s in subruns)
    estimated_total_wall_clock_s = sum(s["estimated_wall_clock_s"] for s in subruns)

    caps_satisfied = True
    if caps["cost_latency_cap_token_budget"] is not None:
        if estimated_total_tokens > caps["cost_latency_cap_token_budget"]:
            caps_satisfied = False
            blockers.append(
                f"estimated_tokens_exceeds_cap:{estimated_total_tokens}_gt_{caps['cost_latency_cap_token_budget']}"
            )
    if caps["cost_latency_cap_wall_clock_s"] is not None:
        if estimated_total_wall_clock_s > caps["cost_latency_cap_wall_clock_s"]:
            caps_satisfied = False
            blockers.append(
                f"estimated_wall_clock_exceeds_cap:{estimated_total_wall_clock_s}_gt_{caps['cost_latency_cap_wall_clock_s']}"
            )

    artifact = {
        "artifact_kind": "abhe_v0_per_case_scorer_slicer_rerun_manifest",
        "schema_version": "abhe_v0_per_case_scorer_slicer_rerun_manifest_v0",
        "run_scope": "planning_only_no_provider_no_bfcl_no_scorer_call",
        "bounded_dev_smoke_only": True,
        "raw_material_absent": True,
        "performance_evidence": False,
        "holdout_touched": False,
        "full_suite_touched": False,
        "archive_updated": False,
        "scorer_diff_committed": False,
        "raw_provider_payload_committed": False,
        "raw_bfcl_result_tree_committed": False,
        "gold_expected_committed": False,
        "argument_values_committed": False,
        "prompt_literal_committed": False,
        "provider_calls_made": False,
        "bfcl_generate_called": False,
        "bfcl_evaluate_called": False,
        "scorer_called": False,
        "runtime_wired_into_proxy": False,
        "huawei_acceptance_ready": False,
        "sota_3pp_claim_ready": False,
        "signed_approval_packet_path": str(SIGNED_PACKET.relative_to(REPO_ROOT)),
        "signed_approval_packet_sha256": _sha256(SIGNED_PACKET),
        "source_matrix_path": str(SOURCE_MATRIX.relative_to(REPO_ROOT)),
        "source_matrix_sha256": _sha256(SOURCE_MATRIX),
        "target_category": EXPECTED_TARGET,
        "approved_arms": EXPECTED_ARMS,
        "target_case_count": EXPECTED_TARGET_CASE_COUNT,
        "expected_subrun_count": expected_subrun_count,
        "expected_post_slicing_unique_scorer_unit_count_for_target": EXPECTED_TARGET_CASE_COUNT,
        "expected_post_slicing_compact_to_scorer_unit_factor": 1.0,
        "current_pre_slicing_unique_scorer_unit_count_for_target": pre_slicing_unique_scorer_units,
        "subruns": subruns,
        "estimated_total_tokens": estimated_total_tokens,
        "estimated_total_wall_clock_s": estimated_total_wall_clock_s,
        "caps_from_signed_packet": caps,
        "caps_satisfied_by_estimate": caps_satisfied,
        "executor_ready_to_proceed": (caps_satisfied and not blockers),
        "executor_actually_executed": False,
        "blockers": blockers,
    }

    if strict:
        bad = set(artifact.keys()) - ALLOWED_TOP_KEYS
        if bad:
            raise ValueError("non_whitelisted_top_keys:" + ",".join(sorted(bad)))
        for sub in subruns:
            sbad = set(sub.keys()) - ALLOWED_SUBRUN_KEYS
            if sbad:
                raise ValueError("non_whitelisted_subrun_keys:" + ",".join(sorted(sbad)))
        cbad = set(caps.keys()) - ALLOWED_CAPS_KEYS
        if cbad:
            raise ValueError("non_whitelisted_caps_keys:" + ",".join(sorted(cbad)))
        _scan_forbidden(artifact)

    return artifact


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    art = build(strict=args.strict)
    if args.write:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(art, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.compact:
        compact = {
            "abhe_v0_per_case_scorer_slicer_rerun_manifest_passed": (
                not art["blockers"] and art["executor_ready_to_proceed"]
            ),
            "target_category": art["target_category"],
            "target_case_count": art["target_case_count"],
            "approved_arms": art["approved_arms"],
            "expected_subrun_count": art["expected_subrun_count"],
            "expected_post_slicing_unique_scorer_unit_count_for_target":
                art["expected_post_slicing_unique_scorer_unit_count_for_target"],
            "current_pre_slicing_unique_scorer_unit_count_for_target":
                art["current_pre_slicing_unique_scorer_unit_count_for_target"],
            "estimated_total_tokens": art["estimated_total_tokens"],
            "estimated_total_wall_clock_s": art["estimated_total_wall_clock_s"],
            "caps_from_signed_packet": art["caps_from_signed_packet"],
            "caps_satisfied_by_estimate": art["caps_satisfied_by_estimate"],
            "executor_ready_to_proceed": art["executor_ready_to_proceed"],
            "executor_actually_executed": art["executor_actually_executed"],
            "blockers": art["blockers"],
            "report_scope": "abhe_v0_per_case_scorer_slicer_rerun_manifest_build",
        }
        print(json.dumps(compact, ensure_ascii=False))
    else:
        print(json.dumps(art, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
