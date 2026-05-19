"""
Boundary tests for P1.5b per-case scorer slicer approval packet.

Hard contract:
  - packet present, well-formed structure
  - approval_status == 'draft_pending_signature' by default
  - all AUTHORIZATION_FIELDS False while draft_pending_signature
  - all FORCED_FALSE fields False
  - all REQUIRED_STOP_LOSS entries present
  - signature fields present but unsigned (placeholders/null)
  - non-strict checker exits 0 (well-formed structurally)
  - strict checker exits 1 (unsigned = unauthorized)
  - hypothetically-signed packet (tmp copy with all fields filled +
    approval_status='approved' + all 6 auth fields True) passes strict
"""
from __future__ import annotations
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_PYPATH = str(REPO) + ":" + str(REPO / "src")
CHECKER = REPO / "scripts/check_abhe_v0_per_case_scorer_slicer_approval_packet.py"
PACKET = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_approval_packet.json"

AUTH_FIELDS = [
    "authorized", "provider_calls_authorized", "bfcl_generate_authorized",
    "bfcl_evaluate_authorized", "scorer_authorized",
    "per_case_scorer_invocation_authorized",
]
FORCED_FALSE = [
    "holdout_authorized", "full_suite_authorized", "archive_update_authorized",
    "performance_claim_authorized", "performance_evidence",
    "sota_3pp_claim_ready", "huawei_acceptance_ready",
    "raw_outputs_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "scorer_diff_committed", "prompt_literal_committed",
    "argument_values_committed",
]
REQUIRED_STOP_LOSS = {
    "raw_leakage", "provider_model_protocol_mismatch", "case_list_hash_mismatch",
    "scorer_unit_alignment_mismatch", "runner_manifest_incompatible",
    "runtime_config_missing_or_mismatch", "cost_latency_cap_exceeded",
    "regression_cap_exceeded", "scorer_artifact_schema_failure",
    "per_case_scorer_call_count_mismatch", "provider_504_rate_exceeded",
}
SIG_FIELDS = [
    "signed_by", "signed_at_iso8601_utc", "signed_at_commit_sha",
    "cost_latency_cap_token_budget", "cost_latency_cap_wall_clock_s",
    "regression_cap_error_class_delta_max_cases",
    "cost_amplification_cap_factor", "provider_504_rate_cap_pct",
]


def _run(args, env_extra=None):
    env = {"PYTHONPATH": _PYPATH, "PATH": "/usr/bin:/bin"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(args, capture_output=True, text=True, cwd=str(REPO), env=env)


def _load():
    return json.loads(PACKET.read_text(encoding="utf-8"))


def test_packet_exists_and_is_json():
    assert PACKET.exists()
    d = _load()
    assert d["artifact_kind"] == "abhe_v0_per_case_scorer_slicer_approval_packet"
    assert d["schema_version"] == "abhe_v0_per_case_scorer_slicer_approval_packet_v0"


def test_default_status_is_draft_pending_signature():
    d = _load()
    assert d["approval_status"] == "draft_pending_signature"


def test_all_authorization_fields_false_in_draft():
    d = _load()
    for k in AUTH_FIELDS:
        assert d[k] is False, f"{k}_must_be_false_in_draft"


def test_all_forced_false_fields_are_false():
    d = _load()
    for k in FORCED_FALSE:
        assert d[k] is False, f"{k}_not_false"


def test_required_stop_loss_present():
    d = _load()
    assert REQUIRED_STOP_LOSS.issubset(set(d["stop_loss"]))


def test_signature_block_present_but_unsigned():
    d = _load()
    sig = d["signature_block"]
    for f in SIG_FIELDS:
        assert f in sig, f"signature_field_{f}_missing"
    assert sig["signed_by"] == "<unsigned>"
    assert sig["signed_at_iso8601_utc"] == "<unsigned>"
    assert sig["signed_at_commit_sha"] == "<unsigned>"
    assert sig["cost_latency_cap_token_budget"] is None
    assert sig["cost_latency_cap_wall_clock_s"] is None
    assert sig["regression_cap_error_class_delta_max_cases"] is None
    assert sig["cost_amplification_cap_factor"] is None
    assert sig["provider_504_rate_cap_pct"] is None


def test_artifact_boundary_compact_only():
    d = _load()
    b = d["artifact_boundary"]
    assert b["compact_only"] is True
    for k in ["raw_outputs_committed", "raw_provider_payload_committed",
              "raw_bfcl_result_tree_committed", "gold_expected_committed",
              "scorer_diff_committed", "prompt_literal_committed",
              "argument_values_committed"]:
        assert b[k] is False


def test_pre_rerun_dependencies_consistent():
    d = _load()
    pre = d["pre_rerun_dependencies"]
    assert pre["p2_v3_skeleton_merged"] is True
    assert pre["p3_backoff_policy_declarative_only_merged"] is True
    assert pre["p3_backoff_policy_wired_into_proxy"] is False
    assert pre["same_case_id_hash_as_p1"] is True
    assert pre["p1_score_adapter_artifact_present"] is True


def test_p1_score_adapter_artifact_actually_present_on_disk():
    p = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_true_per_selected_id_score_adapter.json"
    assert p.exists(), "p1_score_adapter_artifact_should_be_present"


def test_runtime_config_path_exists():
    d = _load()
    rt = REPO / d["approved_runtime_config_path"]
    assert rt.exists()


def test_checker_default_mode_exits_0_well_formed():
    p = _run([sys.executable, str(CHECKER), "--compact"])
    assert p.returncode == 0, f"default mode rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["approval_packet_passed"] is True
    assert out["authorized"] is False
    assert out["approval_status"] == "draft_pending_signature"


def test_checker_strict_mode_exits_1_unsigned():
    p = _run([sys.executable, str(CHECKER), "--compact", "--strict"])
    assert p.returncode == 1, f"strict mode rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["approval_packet_passed"] is False
    assert "approval_status_not_approved_in_strict_mode" in out["blockers"]


def test_checker_strict_mode_passes_when_signed_hypothetically():
    """Create a temp copy of the packet with all signature fields filled,
    approval_status='approved', all 6 AUTHORIZATION_FIELDS True. Strict
    checker should exit 0.

    This test does NOT modify the on-disk packet. It only proves the
    checker correctly transitions to authorized when all fields are set."""
    d = _load()
    d["approval_status"] = "approved"
    for k in AUTH_FIELDS:
        d[k] = True
    d["signature_block"]["signed_by"] = "test_reviewer_synthetic"
    d["signature_block"]["signed_at_iso8601_utc"] = "2026-01-01T00:00:00Z"
    d["signature_block"]["signed_at_commit_sha"] = "synthetic_commit_sha_for_test"
    d["signature_block"]["cost_latency_cap_token_budget"] = 1_000_000
    d["signature_block"]["cost_latency_cap_wall_clock_s"] = 1800
    d["signature_block"]["regression_cap_error_class_delta_max_cases"] = 2
    d["signature_block"]["cost_amplification_cap_factor"] = 5.0
    d["signature_block"]["provider_504_rate_cap_pct"] = 5.0
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        json.dump(d, f)
        tmp_path = f.name
    try:
        p = _run([sys.executable, str(CHECKER), "--packet", tmp_path, "--compact", "--strict"])
        assert p.returncode == 0, f"signed-hypothesis rc={p.returncode}\n{p.stdout}\n{p.stderr}"
        out = json.loads(p.stdout.strip().splitlines()[-1])
        assert out["approval_packet_passed"] is True
        assert out["approval_status"] == "approved"
        assert out["authorized"] is True
        assert out["per_case_scorer_invocation_authorized"] is True
    finally:
        os.unlink(tmp_path)


def test_checker_rejects_inconsistent_authorized_true_in_draft():
    """If anyone hand-edits authorized=True while status remains draft,
    the checker must flag it. Defense against accidental privilege escalation."""
    d = _load()
    d["authorized"] = True  # corrupt
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        json.dump(d, f)
        tmp_path = f.name
    try:
        p = _run([sys.executable, str(CHECKER), "--packet", tmp_path, "--compact"])
        out = json.loads(p.stdout.strip().splitlines()[-1])
        assert out["approval_packet_passed"] is False
        assert any("authorized_must_be_false_while_draft" in b for b in out["blockers"])
    finally:
        os.unlink(tmp_path)


def test_checker_rejects_forced_false_violation():
    """If anyone sets holdout_authorized=True even after signing, the
    checker must still reject because holdout/full/archive/perf/sota/huawei
    are NEVER authorized by this packet."""
    d = _load()
    d["approval_status"] = "approved"
    for k in AUTH_FIELDS:
        d[k] = True
    d["holdout_authorized"] = True  # boundary violation
    for f in SIG_FIELDS:
        if f == "signed_by":
            d["signature_block"][f] = "x"
        elif f in ("signed_at_iso8601_utc", "signed_at_commit_sha"):
            d["signature_block"][f] = "x"
        else:
            d["signature_block"][f] = 1
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        json.dump(d, f)
        tmp_path = f.name
    try:
        p = _run([sys.executable, str(CHECKER), "--packet", tmp_path, "--compact", "--strict"])
        assert p.returncode == 1
        out = json.loads(p.stdout.strip().splitlines()[-1])
        assert "holdout_authorized_not_false" in out["blockers"]
    finally:
        os.unlink(tmp_path)


def test_checker_rejects_missing_stop_loss_trigger():
    d = _load()
    d["stop_loss"] = ["raw_leakage"]  # incomplete
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        json.dump(d, f)
        tmp_path = f.name
    try:
        p = _run([sys.executable, str(CHECKER), "--packet", tmp_path, "--compact"])
        out = json.loads(p.stdout.strip().splitlines()[-1])
        assert out["approval_packet_passed"] is False
        assert "stop_loss_incomplete" in out["blockers"]
    finally:
        os.unlink(tmp_path)


def test_pre_slicing_scorer_unit_count_acknowledged():
    """The packet explicitly records the current pre-slicing state
    (unique_scorer_unit_count == 1) as part of the honest justification
    for why slicing is needed."""
    d = _load()
    assert d["current_target_unique_scorer_unit_count_pre_slicing"] == 1
    assert d["approved_target_unique_scorer_unit_count_post_slicing"] == 24
