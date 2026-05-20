#!/usr/bin/env python3
"""
build_session_status
====================
Read-only status dashboard generator for the training-free / ABHE-v0 repo.

Emits:
  - outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_session_status.json
  - STATUS.md (top-level, human-readable)

What it inspects (all read-only):
  - current branch + HEAD sha + origin sha
  - working tree dirty?
  - count of checkers in scripts/check_abhe_*.py
  - count of test files in tests/test_abhe_*.py
  - signing status of P1.5b approval packet
  - boundary attestation fields across all known artifact JSONs

Designed so CLAUDE_RESUME.md no longer needs hand-editing of dynamic
numbers — the builder is the single source of truth.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/build_session_status.py --compact --strict --write
"""
from __future__ import annotations
import argparse, json, subprocess, sys, hashlib, glob, pathlib
from datetime import datetime, timezone

REPO = pathlib.Path(".").resolve()
ARTIFACT_DIR = REPO / "outputs" / "artifacts" / "stage1_bfcl_acceptance"
OUT_JSON = ARTIFACT_DIR / "abhe_v0_session_status.json"
OUT_MD = REPO / "STATUS.md"

BOUNDARY_FIELDS = [
    "archive_updated", "argument_values_committed", "bfcl_evaluate_called",
    "bfcl_generate_called", "full_suite_touched", "gold_expected_committed",
    "holdout_touched", "huawei_acceptance_ready", "performance_evidence",
    "prompt_literal_committed", "provider_calls_made",
    "raw_bfcl_result_tree_committed", "raw_provider_payload_committed",
    "runtime_wired_into_proxy", "scorer_called", "scorer_diff_committed",
    "sota_3pp_claim_ready",
]

# Pre-sprint baseline evidence artifacts. These ARE allowed to have
# bfcl_*/provider/scorer = true because they predate the fail-closed sprint
# and serve as historical evidence. The boundary commitment says "this sprint
# does not touch these", which is satisfied as long as NO NEW artifact with
# true values appears outside this set.
# Review and update this list whenever a new baseline is rolled.
PRE_SPRINT_BASELINE_ARTIFACTS = {
    "abhe_v0_expanded_bfcl_dev_smoke_result.json",
    "abhe_v0_expanded_bfcl_dev_smoke_result_v1_snapshot.json",
    "abhe_v0_bfcl_dev_smoke_result.json",
    "abhe_v0_bfcl_dev_smoke_execution_failure.json",
    "abhe_v0_runtime_slot_controller_distinct_rerun_failure.json",
    "abhe_v0_provider_preflight.json",
}

# Sprint-scope artifacts that document a real, signed-packet-authorized
# run. These ARE allowed to have provider_calls_made / bfcl_*_called /
# scorer_called = true because that is the honest record of what
# happened under the signed packet. Such artifacts must still have all
# OTHER boundary attestations (raw_*, holdout, full_suite, archive,
# performance, sota, huawei) = false, AND must NOT contain raw material.
# Review when a new approved-run evidence artifact lands.

# Artifacts explicitly authorized by the user to contain raw prompts,
# argument values, or gold state for debug purposes. These ARE allowed
# to have raw_prompt_committed=true, argument_values_committed=true,
# prompt_literal_committed=true, raw_material_absent=false. They MUST
# still have raw_provider_payload_committed=false,
# raw_bfcl_result_tree_committed=false, scorer_diff_committed=false,
# performance_evidence=false, holdout_touched=false, etc.
USER_AUTHORIZED_DIAGNOSTIC_EXTRACTION_ARTIFACTS = {
    "abhe_v0_e9_debug_extended_with_raw_traces.json",
    "abhe_v0_e9_final_root_cause_with_raw_extraction.json",
}

APPROVED_RUN_EVIDENCE_ARTIFACTS = {
    # G6b-2: live baseline arm residual smoke under signed P1.5b packet
    "abhe_v0_baseline_arm_residual_smoke_per_case_diagnostic.json",
    # cf2-partial: conditional_frozen_v2 arm under signed packet (subprocess
    # timeout after 19/24 cases; partial result preserved for arm comparison)
    "abhe_v0_cf2_partial_per_case_diagnostic.json",
    # candidate-vs-baseline comparison artifact (read-only of the above two)
    "abhe_v0_baseline_vs_cf2_per_case_comparison.json",
    # 3-way target-category comparison (gpt-4.1 baseline, cf2_partial, gpt-4o baseline)
    "abhe_v0_target_category_three_way_comparison.json",
    # baseline arm complete run on gpt-4o (all 6 categories, 0/48)
    "abhe_v0_baseline_gpt4o_per_case_diagnostic.json",
}

# Boundary fields that MUST remain false even for approved-run-evidence
# artifacts. These are the true "never-touched" invariants. Different
# from BOUNDARY_FIELDS which includes runtime-execution markers that are
# legitimately true for evidence artifacts.
NEVER_TRUE_FIELDS = [
    "archive_updated", "argument_values_committed", "full_suite_touched",
    "gold_expected_committed", "holdout_touched", "huawei_acceptance_ready",
    "performance_evidence", "prompt_literal_committed",
    "raw_bfcl_result_tree_committed", "raw_provider_payload_committed",
    "runtime_wired_into_proxy", "scorer_diff_committed",
    "sota_3pp_claim_ready",
]

# Files written BY this builder; excluded from the self-dirty check
# so that running the builder doesn't make its own next run report
# "working_tree_dirty".
SELF_OUTPUT_FILES = {
    "STATUS.md",
    "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_session_status.json",
}


def sh(cmd: list[str]) -> str:
    return subprocess.run(cmd, capture_output=True, text=True, check=False).stdout.strip()


def _dirty_excluding_self_outputs() -> bool:
    """Return True iff the working tree has any uncommitted changes
    other than the builder's own output files (STATUS.md +
    abhe_v0_session_status.json). Running the builder dirties those by
    design; we don't want it to flag itself.

    Note: must NOT use sh() here because sh() strips leading whitespace,
    which breaks position-based parsing of " M PATH" (single-space-prefix
    indicates work-tree-modified-only). Use subprocess directly with -z
    or split-from-first-whitespace to avoid the strip issue.
    """
    # Use subprocess directly (without .strip) for robust parsing.
    raw = subprocess.run(
        ["git", "status", "--short"],
        capture_output=True, text=True, check=False
    ).stdout
    if not raw.strip():
        return False
    for line in raw.splitlines():
        if not line:
            continue
        # First two columns are X (index) and Y (worktree) status codes,
        # then one space, then the path (which may contain spaces).
        # If a path is renamed, format is "R<old> -> <new>"; we handle that
        # by taking the substring after the first " " at index >= 2.
        if len(line) < 3:
            return True
        path = line[3:]
        # Strip quoting if git --short quoted the path
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        # Rename detection: "old -> new" — check both sides
        if " -> " in path:
            old_p, new_p = path.split(" -> ", 1)
            paths = (old_p.strip(), new_p.strip())
        else:
            paths = (path,)
        for p in paths:
            if p not in SELF_OUTPUT_FILES:
                return True
    return False


def collect_git() -> dict:
    branch = sh(["git", "branch", "--show-current"])
    head = sh(["git", "rev-parse", "HEAD"])
    ls = sh(["git", "ls-remote", "origin", branch]) if branch else ""
    parts = ls.split()
    origin_head = parts[0] if parts else ""
    return {
        "branch": branch,
        "head": head,
        "origin_head": origin_head,
        "origin_synced": bool(origin_head) and origin_head == head,
        "branch_published": bool(origin_head),
        "dirty": _dirty_excluding_self_outputs(),
        "last_commit": sh(["git", "log", "-1", "--format=%h %s"]),
    }


def collect_codebase() -> dict:
    checkers = sorted(glob.glob("scripts/check_abhe_*.py"))
    tests = sorted(glob.glob("tests/test_abhe_*.py"))
    return {
        "checker_count": len(checkers),
        "checker_files": [pathlib.Path(p).name for p in checkers],
        "test_file_count": len(tests),
        "test_files": [pathlib.Path(p).name for p in tests],
    }


def collect_packet_status() -> dict:
    p = ARTIFACT_DIR / "abhe_v0_per_case_scorer_slicer_approval_packet.json"
    if not p.exists():
        return {"present": False}
    d = json.loads(p.read_text())
    return {
        "present": True,
        "approval_status": d.get("approval_status"),
        "authorized": d.get("authorized"),
        "signed_by": d.get("signature_block", {}).get("signed_by") if isinstance(d.get("signature_block"), dict) else None,
        "caps": {
            k: d.get("signature_block", {}).get(k) if isinstance(d.get("signature_block"), dict) else None
            for k in [
                "cost_latency_cap_token_budget",
                "cost_latency_cap_wall_clock_s",
                "regression_cap_error_class_delta_max_cases",
                "cost_amplification_cap_factor",
                "provider_504_rate_cap_pct",
            ]
        },
    }


def collect_boundary_attestation() -> dict:
    """Scope-aware boundary scan with three categories:

    1. PRE_SPRINT_BASELINE_ARTIFACTS — pre-sprint historical evidence.
       Allowed to have any BOUNDARY_FIELDS = true. Recorded as
       `pre_sprint_baseline_state` (informational only).

    2. APPROVED_RUN_EVIDENCE_ARTIFACTS — sprint artifacts that document
       a real run authorized by a signed packet. Allowed to have
       provider_calls_made / bfcl_*_called / scorer_called = true (the
       honest record of what the signed packet authorized). Must still
       have NEVER_TRUE_FIELDS = false. Recorded as
       `approved_run_evidence_state` (informational) + drift if any
       NEVER_TRUE_FIELDS is true.

    3. All other sprint artifacts (policy / declarative / dry-run /
       skeleton) — MUST have ALL BOUNDARY_FIELDS = false. Any true
       value counts as `sprint_violations` -> drift blocker.
    """
    sprint_violations: dict[str, list[str]] = {f: [] for f in BOUNDARY_FIELDS}
    baseline_state: dict[str, list[str]] = {f: [] for f in BOUNDARY_FIELDS}
    approved_evidence_state: dict[str, list[str]] = {f: [] for f in BOUNDARY_FIELDS}
    approved_evidence_violations: dict[str, list[str]] = {f: [] for f in NEVER_TRUE_FIELDS}
    for jf in ARTIFACT_DIR.glob("*.json"):
        try:
            d = json.loads(jf.read_text())
        except Exception:
            continue
        is_baseline = jf.name in PRE_SPRINT_BASELINE_ARTIFACTS
        is_approved_evidence = jf.name in APPROVED_RUN_EVIDENCE_ARTIFACTS
        is_user_authorized_extraction = jf.name in USER_AUTHORIZED_DIAGNOSTIC_EXTRACTION_ARTIFACTS
        for f in BOUNDARY_FIELDS:
            v = d.get(f)
            if v is not True:
                continue
            if is_baseline:
                baseline_state[f].append(jf.name)
            elif is_approved_evidence:
                approved_evidence_state[f].append(jf.name)
                if f in NEVER_TRUE_FIELDS:
                    approved_evidence_violations[f].append(jf.name)
            elif is_user_authorized_extraction:
                approved_evidence_state[f].append(jf.name)
                if f in NEVER_TRUE_FIELDS:
                    approved_evidence_violations[f].append(jf.name)
            else:
                sprint_violations[f].append(jf.name)
    return {
        "sprint_scope_all_false": (
            all(len(v) == 0 for v in sprint_violations.values())
            and all(len(v) == 0 for v in approved_evidence_violations.values())
        ),
        "sprint_violations": {k: v for k, v in sprint_violations.items() if v},
        "approved_evidence_violations": {k: v for k, v in approved_evidence_violations.items() if v},
        "approved_evidence_state": {k: v for k, v in approved_evidence_state.items() if v},
        "pre_sprint_baseline_state": {k: v for k, v in baseline_state.items() if v},
    }


def collect_tags() -> list[str]:
    return [t for t in sh(["git", "tag", "--sort=-creatordate"]).splitlines() if t][:10]


def build(strict: bool, compact: bool) -> tuple[dict, str]:
    payload = {
        "artifact_kind": "abhe_v0_session_status",
        "schema_version": "abhe_v0_session_status_v0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "read_only_status_snapshot_no_side_effects",
        "git": collect_git(),
        "codebase": collect_codebase(),
        "p1_5b_packet": collect_packet_status(),
        "boundary_attestation": collect_boundary_attestation(),
        "recent_tags": collect_tags(),
    }
    blockers: list[str] = []
    if not payload["git"]["head"]:
        blockers.append("no_head")
    if payload["git"]["dirty"]:
        blockers.append("working_tree_dirty")
    if not payload["boundary_attestation"]["sprint_scope_all_false"]:
        blockers.append("sprint_scope_boundary_attestation_drift")
    if not payload["p1_5b_packet"].get("present"):
        blockers.append("p1_5b_packet_missing")
    payload["blockers"] = blockers
    payload["abhe_v0_session_status_passed"] = len(blockers) == 0

    md = render_markdown(payload)
    return payload, md


def render_markdown(p: dict) -> str:
    git = p["git"]
    cb = p["codebase"]
    pk = p["p1_5b_packet"]
    bnd = p["boundary_attestation"]
    L = []
    L.append(f"# STATUS — training-free / ABHE-v0\n")
    L.append(f"_Auto-generated by `scripts/build_session_status.py` at {p['generated_at']}_\n")
    L.append(f"_Do NOT hand-edit. Re-run the builder._\n")
    L.append("## Git")
    L.append(f"- branch: `{git['branch']}`")
    L.append(f"- HEAD: `{git['head']}`")
    if git['branch_published']:
        sync = "✅ synced" if git['origin_synced'] else "⚠️ diverged"
        L.append(f"- origin HEAD: `{git['origin_head']}` ({sync})")
    else:
        L.append(f"- origin HEAD: _(branch not yet published)_")
    L.append(f"- working tree: {'⚠️ dirty' if git['dirty'] else '✅ clean'}")
    L.append(f"- last commit: {git['last_commit']}\n")
    L.append("## Codebase")
    L.append(f"- checkers: **{cb['checker_count']}** files (`scripts/check_abhe_*.py`)")
    L.append(f"- tests: **{cb['test_file_count']}** files (`tests/test_abhe_*.py`)\n")
    L.append("## P1.5b approval packet")
    if pk.get("present"):
        L.append(f"- status: `{pk['approval_status']}`")
        L.append(f"- authorized: `{pk['authorized']}`")
        L.append(f"- signed_by: `{pk['signed_by']}`")
        L.append("- caps:")
        for k, v in pk["caps"].items():
            L.append(f"  - {k}: `{v}`")
    else:
        L.append("- ⚠️ packet missing")
    L.append("")
    L.append("## Boundary attestation (sprint scope)")
    if bnd["sprint_scope_all_false"]:
        L.append("✅ All boundary attestation fields are `false` in sprint-scope artifacts.")
    else:
        L.append("❌ Drift detected in sprint-scope artifacts:")
        for f, files in bnd["sprint_violations"].items():
            L.append(f"- `{f}` = true in: {', '.join(files)}")
    if bnd["pre_sprint_baseline_state"]:
        L.append("")
        L.append("_Pre-sprint baseline evidence (expected, informational only):_")
        for f, files in bnd["pre_sprint_baseline_state"].items():
            L.append(f"- `{f}` = true in: {', '.join(files)}")
    L.append("")
    L.append("## Recent tags")
    if p["recent_tags"]:
        for t in p["recent_tags"]:
            L.append(f"- `{t}`")
    else:
        L.append("(no tags yet)")
    L.append("")
    L.append(f"## Blockers\n{'(none)' if not p['blockers'] else chr(10).join('- ' + b for b in p['blockers'])}\n")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--compact", action="store_true")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    payload, md = build(args.strict, args.compact)
    if args.write:
        ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(payload, indent=2 if not args.compact else None, ensure_ascii=False))
        OUT_MD.write_text(md)

    if args.compact:
        print(json.dumps({k: payload[k] for k in ("abhe_v0_session_status_passed", "blockers", "git", "p1_5b_packet")}, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))

    if args.strict and payload["blockers"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
