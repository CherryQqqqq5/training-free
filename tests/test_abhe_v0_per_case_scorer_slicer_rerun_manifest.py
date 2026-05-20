"""
Boundary tests for G6a per-case scorer slicer rerun manifest.

Hard contract:
  - builder reads signed packet via strict checker; refuses if packet not signed
  - builder reads source matrix; emits 24 x 3 = 72 sub-runs
  - all sub-runs reference the 24 multi_turn_miss_param case_stable_hashes
  - each sub-run records arm + case identifiers (no raw material)
  - estimated_total_tokens <= cost_latency_cap_token_budget
  - estimated_total_wall_clock_s <= cost_latency_cap_wall_clock_s
  - expected_post_slicing_unique_scorer_unit_count_for_target == 24
  - current_pre_slicing_unique_scorer_unit_count_for_target == 1
  - executor_actually_executed remains False (planning-only)
  - no forbidden key substring in any non-attestation key
  - checker exits 0 only when above holds
"""
from __future__ import annotations
import json, os, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_PYPATH = str(REPO) + ":" + str(REPO / "src")
BUILDER = REPO / "scripts/build_abhe_v0_per_case_scorer_slicer_rerun_manifest.py"
CHECKER = REPO / "scripts/check_abhe_v0_per_case_scorer_slicer_rerun_manifest_ready.py"
ARTIFACT = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_rerun_manifest.json"
SIGNED_PACKET = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_approval_packet.json"
SOURCE_MATRIX = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_per_selected_id_matrix.json"

EXPECTED_ARMS = ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]

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

FORBIDDEN_SUBS = ("prompt", "gold", "argument_value",
                  "raw_response", "raw_payload", "scorer_diff")
ATTESTATION_ALLOW_KEYS = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
}


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO),
                          env={"PYTHONPATH": _PYPATH, "PATH": "/usr/bin:/bin"})


def _run_builder(write):
    cmd = [sys.executable, str(BUILDER), "--compact", "--strict"]
    if write:
        cmd.append("--write")
    p = _run(cmd)
    assert p.returncode == 0, f"builder rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    return json.loads(p.stdout.strip().splitlines()[-1])


def _scan_forbidden(obj, path="$"):
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ATTESTATION_ALLOW_KEYS:
                bad += _scan_forbidden(v, f"{path}.{k}")
                continue
            kl = k.lower()
            for sub in FORBIDDEN_SUBS:
                if sub in kl:
                    bad.append(f"{path}.{k}")
            bad += _scan_forbidden(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, x in enumerate(obj):
            bad += _scan_forbidden(x, f"{path}[{i}]")
    return bad


# === Builder tests ===

def test_builder_emits_compact_pass():
    s = _run_builder(False)
    assert s["abhe_v0_per_case_scorer_slicer_rerun_manifest_passed"] is True
    assert s["target_category"] == "multi_turn_miss_param"
    assert s["target_case_count"] == 24
    assert s["expected_subrun_count"] == 72
    assert s["expected_post_slicing_unique_scorer_unit_count_for_target"] == 24
    assert s["current_pre_slicing_unique_scorer_unit_count_for_target"] == 1
    assert s["executor_ready_to_proceed"] is True
    assert s["executor_actually_executed"] is False
    assert s["blockers"] == []


def test_builder_writes_artifact():
    _run_builder(True)
    assert ARTIFACT.exists()


def test_all_attestations_false():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    for k in ATTESTATION_MUST_FALSE:
        assert art[k] is False, f"{k}_must_be_false"


def test_subrun_count_exactly_72():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert len(art["subruns"]) == 72


def test_subruns_cover_24_distinct_case_stable_hashes():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    distinct = {s["case_stable_hash"] for s in art["subruns"]}
    assert len(distinct) == 24, f"expected 24 distinct, got {len(distinct)}"


def test_subruns_cover_three_arms_each_24():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    by_arm = {}
    for s in art["subruns"]:
        by_arm[s["arm"]] = by_arm.get(s["arm"], 0) + 1
    assert by_arm == {a: 24 for a in EXPECTED_ARMS}, f"arm distribution: {by_arm}"


def test_each_subrun_has_only_whitelisted_keys():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    allowed = {
        "subrun_index", "arm", "case_stable_hash", "case_identifier_hash",
        "dataset_raw_id_hash", "selected_index", "selected_index_within_dataset_raw_id",
        "scorer_invocation_mode",
        "estimated_tokens", "estimated_wall_clock_s",
    }
    for s in art["subruns"]:
        extra = set(s.keys()) - allowed
        assert not extra, f"subrun {s.get('subrun_index')} has extra keys: {extra}"


def test_each_subrun_uses_single_case_invocation_mode():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    for s in art["subruns"]:
        assert s["scorer_invocation_mode"] == "single_case_manifest_input"


def test_estimated_tokens_below_signed_cap():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    cap = art["caps_from_signed_packet"]["cost_latency_cap_token_budget"]
    assert art["estimated_total_tokens"] <= cap, (
        f"estimate {art['estimated_total_tokens']} > cap {cap}"
    )


def test_estimated_wall_clock_below_signed_cap():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    cap = art["caps_from_signed_packet"]["cost_latency_cap_wall_clock_s"]
    assert art["estimated_total_wall_clock_s"] <= cap


def test_signed_packet_sha256_matches_disk():
    import hashlib
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    expected = "sha256:" + hashlib.sha256(SIGNED_PACKET.read_bytes()).hexdigest()
    assert art["signed_approval_packet_sha256"] == expected


def test_source_matrix_sha256_matches_disk():
    import hashlib
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    expected = "sha256:" + hashlib.sha256(SOURCE_MATRIX.read_bytes()).hexdigest()
    assert art["source_matrix_sha256"] == expected


def test_no_forbidden_substrings_in_artifact():
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    bad = _scan_forbidden(art)
    assert not bad, f"forbidden substring in keys: {bad}"


# === Refusal test: builder MUST refuse when signed packet is corrupted ===

def test_builder_refuses_if_packet_strict_fails():
    """Synthesize a draft-state packet copy via tempfile + monkey-patch
    via env. Since the builder hardcodes the path, this is awkward; instead
    we verify the documented invariant by reading the builder's strict
    check function directly."""
    sys.path.insert(0, str(REPO))
    from scripts.build_abhe_v0_per_case_scorer_slicer_rerun_manifest import _load_signed_packet, SIGNED_PACKET as PKT  # noqa
    # Copy the on-disk packet, corrupt to draft state, point module-level
    # SIGNED_PACKET to the corrupted copy, then call _load_signed_packet.
    import scripts.build_abhe_v0_per_case_scorer_slicer_rerun_manifest as B
    original = B.SIGNED_PACKET
    try:
        d = json.loads(original.read_text(encoding="utf-8"))
        d["approval_status"] = "draft_pending_signature"
        d["authorized"] = False
        tmp = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json")
        json.dump(d, tmp)
        tmp.close()
        B.SIGNED_PACKET = Path(tmp.name)
        try:
            B._load_signed_packet()
            raise AssertionError("expected_refusal_did_not_happen")
        except ValueError as e:
            assert "signed_packet_strict_check_failed" in str(e) or \
                   "signed_packet_not_in_approved_state" in str(e) or \
                   "signed_packet_not_authorized" in str(e)
    finally:
        B.SIGNED_PACKET = original
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


# === Checker tests ===

def test_checker_exit_0_strict():
    p = _run([sys.executable, str(CHECKER), "--strict"])
    assert p.returncode == 0, f"checker rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    r = json.loads(p.stdout.strip().splitlines()[-1])
    assert r["abhe_v0_per_case_scorer_slicer_rerun_manifest_ready"] is True
    assert r["blockers"] == []


def test_executor_actually_executed_remains_false():
    """G6a contract: this manifest is planning-only. The executor (G6b)
    will produce a separate artifact when it actually runs. The manifest
    itself MUST remain executor_actually_executed=False."""
    art = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert art["executor_actually_executed"] is False
