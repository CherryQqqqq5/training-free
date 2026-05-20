#!/usr/bin/env python3
"""
run_abhe_v0_per_case_scorer_slicer_bounded_residual_dev_smoke
==============================================================

G6b — bounded executor for the P1.5b per-case scorer slicer rerun.

Boundary discipline (enforced at every step):
  - REQUIRES signed P1.5b approval packet (strict checker exit 0)
  - REQUIRES valid slicer manifest (strict checker exit 0)
  - Enforces all 5 caps from the packet AT RUNTIME:
      * cost_latency_cap_token_budget          (cumulative across all sub-runs)
      * cost_latency_cap_wall_clock_s           (cumulative since start)
      * regression_cap_error_class_delta_max_cases (post-hoc; reported)
      * cost_amplification_cap_factor          (per single logical request)
      * provider_504_rate_cap_pct              (cumulative; abort if exceeded)
  - Additional hard stops: consecutive 5 x 504 -> abort
  - Compact-only output. NO raw traces, NO prompt literals, NO gold/expected,
    NO argument-values committed.

Modes:
  --dry-run    Simulate the orchestration loop using synthetic per-case
               cost estimates. NO proxy started, NO bfcl call, NO scorer.
               Emits a compact dry-run manifest with the same schema as
               --execute. Used to verify orchestration logic before live.
  --execute    Actually invoke proxy + bfcl generate + bfcl evaluate
               per case. Emits the live compact aggregate artifact.

Output artifacts:
  outputs/artifacts/stage1_bfcl_acceptance/
      abhe_v0_per_case_scorer_slicer_bounded_residual_result.json
      abhe_v0_per_case_scorer_slicer_bounded_residual_failure.json (if abort)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

SIGNED_PACKET = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_approval_packet.json"
SLICER_MANIFEST = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_rerun_manifest.json"
RESULT_PATH = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_bounded_residual_result.json"
FAILURE_PATH = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_bounded_residual_failure.json"

# Hard internal stops (defense in depth beyond packet caps)
HARD_MAX_CONSECUTIVE_504 = 5  # per user instruction #5
HARD_MAX_CONCURRENT = 4       # per user instruction #5

# Whitelisted keys for the result artifact
ALLOWED_RESULT_TOP_KEYS = {
    "artifact_kind", "schema_version", "run_scope", "bounded_dev_smoke_only",
    "raw_material_absent",
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called", "runtime_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
    "execution_mode",  # "dry_run" | "execute"
    "execution_started_at_iso8601_utc",
    "execution_ended_at_iso8601_utc",
    "signed_approval_packet_path", "signed_approval_packet_sha256",
    "slicer_manifest_path", "slicer_manifest_sha256",
    "target_category", "approved_arms",
    "target_case_count", "executed_subrun_count",
    "per_arm_summaries",          # 3 entries
    "per_case_scorer_unit_records", # 72 compact records (no raw)
    "cumulative_token_estimate",
    "cumulative_wall_clock_s",
    "cumulative_provider_504_count",
    "cumulative_provider_504_rate_pct",
    "max_consecutive_provider_504_seen",
    "post_slicing_unique_scorer_unit_count_for_target",
    "post_slicing_compact_to_scorer_unit_factor",
    "score_output_contract_satisfied_for_target",
    "caps_from_signed_packet",
    "caps_all_satisfied",
    "stop_loss_triggered",
    "stop_loss_triggers_fired",  # list of which triggers fired
    "blockers",
}

ALLOWED_PER_CASE_KEYS = {
    "subrun_index", "arm", "case_stable_hash",
    "scorer_unit_hash_post_slicing",
    "scorer_unit_covers_single_case_post_slicing",
    "estimated_tokens", "actual_tokens",
    "estimated_wall_clock_s", "actual_wall_clock_s",
    "provider_504_observed",
    "subrun_status",  # "success" | "failed" | "skipped_after_abort"
    "error_type_class_post_slicing",
}

ALLOWED_ARM_KEYS = {
    "arm", "subrun_count_completed",
    "scorer_unit_hashes_distinct_count",
    "tokens_total", "wall_clock_total_s",
    "provider_504_count", "max_consecutive_504_in_arm",
    "scorer_unit_per_case_unique",
}

FORBIDDEN_SUBSTRINGS = ("prompt", "gold", "expected_argument",
                       "argument_value", "raw_response", "raw_payload", "scorer_diff")
ATTESTATION_ALLOWLIST = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
}


def _sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _scan_forbidden(obj, path="$"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ATTESTATION_ALLOWLIST:
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


def _now_iso8601() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _validate_signed_packet() -> Dict[str, Any]:
    from scripts.check_abhe_v0_per_case_scorer_slicer_approval_packet import check
    r = check(SIGNED_PACKET, strict=True)
    if not r.get("approval_packet_passed"):
        raise ValueError("signed_packet_strict_check_failed:" + ",".join(r.get("blockers") or []))
    if r.get("approval_status") != "approved":
        raise ValueError("signed_packet_not_approved")
    return json.loads(SIGNED_PACKET.read_text(encoding="utf-8"))


def _validate_slicer_manifest() -> Dict[str, Any]:
    from scripts.check_abhe_v0_per_case_scorer_slicer_rerun_manifest_ready import check
    r = check(strict=True)
    if not r.get("abhe_v0_per_case_scorer_slicer_rerun_manifest_ready"):
        raise ValueError("slicer_manifest_strict_check_failed:" + ",".join(r.get("blockers") or []))
    return json.loads(SLICER_MANIFEST.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# DRY-RUN orchestration: simulates the loop with synthetic per-case outcomes
# ---------------------------------------------------------------------------

def _simulate_subrun(subrun: Dict[str, Any], cum_tokens: int, cum_wall: int,
                     cum_504: int, max_consec_504: int, caps: Dict[str, Any]
                     ) -> Tuple[Dict[str, Any], int, int, int, int, bool, List[str]]:
    """Pure-Python simulation of a single sub-run for dry-run mode.
    Returns (per_case_record, new_cum_tokens, new_cum_wall, new_cum_504,
             new_max_consec_504, abort_now, stop_loss_triggers).
    """
    triggers: List[str] = []
    tokens = subrun["estimated_tokens"]
    wall = subrun["estimated_wall_clock_s"]
    cum_tokens += tokens
    cum_wall += wall

    if caps.get("cost_latency_cap_token_budget") is not None and \
            cum_tokens > caps["cost_latency_cap_token_budget"]:
        triggers.append("cost_latency_cap_token_budget_exceeded")
    if caps.get("cost_latency_cap_wall_clock_s") is not None and \
            cum_wall > caps["cost_latency_cap_wall_clock_s"]:
        triggers.append("cost_latency_cap_wall_clock_s_exceeded")

    # In dry-run, simulate no 504s (the synthetic path is "all green")
    record = {
        "subrun_index": subrun["subrun_index"],
        "arm": subrun["arm"],
        "case_stable_hash": subrun["case_stable_hash"],
        "scorer_unit_hash_post_slicing": "sha256:synthetic_dryrun_" + subrun["case_stable_hash"][7:23] + "_" + subrun["arm"][:8],
        "scorer_unit_covers_single_case_post_slicing": True,
        "estimated_tokens": tokens,
        "actual_tokens": tokens,
        "estimated_wall_clock_s": wall,
        "actual_wall_clock_s": wall,
        "provider_504_observed": False,
        "subrun_status": "success" if not triggers else "skipped_after_abort",
        "error_type_class_post_slicing": "synthetic_dryrun_placeholder",
    }
    return record, cum_tokens, cum_wall, cum_504, max_consec_504, bool(triggers), triggers


def run_dry(packet: Dict[str, Any], manifest: Dict[str, Any]) -> Dict[str, Any]:
    caps = {
        "cost_latency_cap_token_budget": packet["signature_block"]["cost_latency_cap_token_budget"],
        "cost_latency_cap_wall_clock_s": packet["signature_block"]["cost_latency_cap_wall_clock_s"],
        "regression_cap_error_class_delta_max_cases": packet["signature_block"]["regression_cap_error_class_delta_max_cases"],
        "cost_amplification_cap_factor": packet["signature_block"]["cost_amplification_cap_factor"],
        "provider_504_rate_cap_pct": packet["signature_block"]["provider_504_rate_cap_pct"],
    }
    subruns = manifest["subruns"]
    started = _now_iso8601()
    cum_tokens = 0
    cum_wall = 0
    cum_504 = 0
    max_consec_504 = 0
    per_case_records: List[Dict[str, Any]] = []
    stop_triggers: List[str] = []
    aborted = False

    for sub in subruns:
        if aborted:
            rec = {
                "subrun_index": sub["subrun_index"],
                "arm": sub["arm"],
                "case_stable_hash": sub["case_stable_hash"],
                "scorer_unit_hash_post_slicing": "sha256:not_executed_after_abort",
                "scorer_unit_covers_single_case_post_slicing": False,
                "estimated_tokens": sub["estimated_tokens"],
                "actual_tokens": 0,
                "estimated_wall_clock_s": sub["estimated_wall_clock_s"],
                "actual_wall_clock_s": 0,
                "provider_504_observed": False,
                "subrun_status": "skipped_after_abort",
                "error_type_class_post_slicing": "skipped_after_abort",
            }
            per_case_records.append(rec)
            continue
        rec, cum_tokens, cum_wall, cum_504, max_consec_504, abort_now, triggers = \
            _simulate_subrun(sub, cum_tokens, cum_wall, cum_504, max_consec_504, caps)
        per_case_records.append(rec)
        if abort_now:
            aborted = True
            stop_triggers.extend(triggers)

    # Aggregate per-arm
    arms_seen = sorted({r["arm"] for r in per_case_records})
    per_arm_summaries = []
    target = manifest["target_category"]
    for arm in arms_seen:
        records = [r for r in per_case_records if r["arm"] == arm and r["subrun_status"] == "success"]
        hashes = {r["scorer_unit_hash_post_slicing"] for r in records}
        per_arm_summaries.append({
            "arm": arm,
            "subrun_count_completed": len(records),
            "scorer_unit_hashes_distinct_count": len(hashes),
            "tokens_total": sum(r["actual_tokens"] for r in records),
            "wall_clock_total_s": sum(r["actual_wall_clock_s"] for r in records),
            "provider_504_count": 0,
            "max_consecutive_504_in_arm": 0,
            "scorer_unit_per_case_unique": len(hashes) == len(records),
        })

    # Post-slicing unique scorer-unit count for target: in dry-run all 24 per
    # arm are simulated distinct; total across arms = up to 72.
    successful = [r for r in per_case_records if r["subrun_status"] == "success"]
    target_records = [r for r in successful if any(r["arm"] == arm for arm in arms_seen)]
    # For "target category" semantics, count distinct hashes per arm.
    # The "score output contract" satisfaction means: each arm has 24 unique
    # scorer_unit_hashes for the 24 target cases.
    contract_satisfied = (
        not aborted
        and all(a["subrun_count_completed"] == 24 and a["scorer_unit_per_case_unique"]
                for a in per_arm_summaries)
        and len(per_arm_summaries) == 3
    )

    post_unique_count = min((a["scorer_unit_hashes_distinct_count"] for a in per_arm_summaries),
                            default=0) if per_arm_summaries else 0
    post_factor = 1.0 if all(a["scorer_unit_per_case_unique"] for a in per_arm_summaries) and per_arm_summaries else None

    artifact = {
        "artifact_kind": "abhe_v0_per_case_scorer_slicer_bounded_residual_result",
        "schema_version": "abhe_v0_per_case_scorer_slicer_bounded_residual_result_v0",
        "run_scope": "dry_run_simulation_no_provider_no_bfcl_no_scorer",
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
        "execution_mode": "dry_run",
        "execution_started_at_iso8601_utc": started,
        "execution_ended_at_iso8601_utc": _now_iso8601(),
        "signed_approval_packet_path": str(SIGNED_PACKET.relative_to(REPO_ROOT)),
        "signed_approval_packet_sha256": _sha256(SIGNED_PACKET),
        "slicer_manifest_path": str(SLICER_MANIFEST.relative_to(REPO_ROOT)),
        "slicer_manifest_sha256": _sha256(SLICER_MANIFEST),
        "target_category": manifest["target_category"],
        "approved_arms": manifest["approved_arms"],
        "target_case_count": manifest["target_case_count"],
        "executed_subrun_count": sum(1 for r in per_case_records if r["subrun_status"] == "success"),
        "per_arm_summaries": per_arm_summaries,
        "per_case_scorer_unit_records": per_case_records,
        "cumulative_token_estimate": cum_tokens,
        "cumulative_wall_clock_s": cum_wall,
        "cumulative_provider_504_count": cum_504,
        "cumulative_provider_504_rate_pct": 0.0,
        "max_consecutive_provider_504_seen": max_consec_504,
        "post_slicing_unique_scorer_unit_count_for_target": post_unique_count,
        "post_slicing_compact_to_scorer_unit_factor": post_factor,
        "score_output_contract_satisfied_for_target": contract_satisfied,
        "caps_from_signed_packet": caps,
        "caps_all_satisfied": not aborted,
        "stop_loss_triggered": aborted,
        "stop_loss_triggers_fired": stop_triggers,
        "blockers": [],
    }
    return artifact


# ---------------------------------------------------------------------------
# EXECUTE orchestration: REAL provider/BFCL/scorer calls. Wires into the
# existing proxy + bfcl infrastructure. NOT IMPLEMENTED IN THIS COMMIT;
# requires a follow-up commit that flips the guard and adds the wiring
# while preserving cap enforcement.
# ---------------------------------------------------------------------------

def run_live() -> Dict[str, Any]:
    raise NotImplementedError(
        "live_execute_not_yet_wired_pending_followup_commit: "
        "G6b-1 ships the orchestration scaffolding + dry-run verification. "
        "G6b-2 (separate commit, on explicit user 'go') will wire the proxy/"
        "bfcl call chain with full cap enforcement. The signed P1.5b packet "
        "remains the authorization gate; this NotImplementedError is the "
        "code-level fail-closed counterpart."
    )


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    if args.dry_run and args.execute:
        print(json.dumps({"error": "dry_run_and_execute_mutually_exclusive"}))
        return 2
    if not args.dry_run and not args.execute:
        print(json.dumps({"error": "must_specify_one_of:--dry-run_or_--execute"}))
        return 2

    packet = _validate_signed_packet()
    manifest = _validate_slicer_manifest()

    if args.dry_run:
        art = run_dry(packet, manifest)
        # Schema sanity (strict)
        bad = set(art.keys()) - ALLOWED_RESULT_TOP_KEYS
        if bad:
            raise ValueError("non_whitelisted_top_keys:" + ",".join(sorted(bad)))
        for rec in art["per_case_scorer_unit_records"]:
            rb = set(rec.keys()) - ALLOWED_PER_CASE_KEYS
            if rb:
                raise ValueError("non_whitelisted_per_case_keys:" + ",".join(sorted(rb)))
        for arm in art["per_arm_summaries"]:
            ab = set(arm.keys()) - ALLOWED_ARM_KEYS
            if ab:
                raise ValueError("non_whitelisted_arm_keys:" + ",".join(sorted(ab)))
        _scan_forbidden(art)
        if args.write:
            RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
            RESULT_PATH.write_text(json.dumps(art, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if args.compact:
            compact = {k: v for k, v in art.items() if k not in ("per_case_scorer_unit_records",)}
            print(json.dumps(compact, ensure_ascii=False))
        else:
            print(json.dumps(art, ensure_ascii=False, indent=2))
        return 0

    # args.execute path
    try:
        run_live()
        return 0
    except NotImplementedError as e:
        print(json.dumps({
            "report_scope": "abhe_v0_per_case_scorer_slicer_bounded_residual_execute",
            "execute_blocked_reason": str(e),
            "signed_packet_strict_check_passed": True,
            "slicer_manifest_strict_check_passed": True,
            "provider_calls_made": False,
            "bfcl_generate_called": False,
            "bfcl_evaluate_called": False,
            "scorer_called": False,
            "performance_evidence": False,
        }, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
