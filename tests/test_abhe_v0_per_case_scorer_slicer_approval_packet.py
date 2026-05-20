"""
Boundary tests for P1.5b per-case scorer slicer approval packet.

Post-G5 (2026-05-20): the on-disk packet is now SIGNED (approval_status='approved',
all 6 AUTHORIZATION_FIELDS True, signature_block fully filled).

Hard contract:
  - packet present, well-formed structure
  - approval_status in {draft_pending_signature, approved, rejected}
  - on-disk: status='approved', all 6 auth fields True, sig fully filled
  - all FORCED_FALSE fields False (boundary discipline regardless of status)
  - all REQUIRED_STOP_LOSS entries present
  - signed caps within sane bounds
  - default checker exits 0 (well-formed, signed)
  - strict checker exits 0 on signed on-disk packet
  - strict checker exits 1 on synthetic draft (tmpfile)
  - rejects privilege escalation (authorized=True in draft state)
  - rejects boundary violation (holdout_authorized=True even when signed)
  - rejects missing stop-loss triggers
"""
from __future__ import annotations
import json, os, subprocess, sys, tempfile
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
    "per_case_scorer_call_count_mismatch", "provider_504_rate_cap_exceeded".replace("_cap", ""),
}
# Fix the set construction above (regression-safe rewrite):
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


def _run(args):
    return subprocess.run(args, capture_output=True, text=True, cwd=str(REPO),
                          env={"PYTHONPATH": _PYPATH, "PATH": "/usr/bin:/bin"})


def _load():
    return json.loads(PACKET.read_text(encoding="utf-8"))


def _make_draft_tmp():
    """Helper: synthesize a draft-state copy of the on-disk packet in
    a tmpfile, return path. Used by draft-state regression tests."""
    d = _load()
    d["approval_status"] = "draft_pending_signature"
    for k in AUTH_FIELDS:
        d[k] = False
    d["signature_block"] = {
        "signed_by": "<unsigned>",
        "signed_at_iso8601_utc": "<unsigned>",
        "signed_at_commit_sha": "<unsigned>",
        "cost_latency_cap_token_budget": None,
        "cost_latency_cap_wall_clock_s": None,
        "regression_cap_error_class_delta_max_cases": None,
        "cost_amplification_cap_factor": None,
        "provider_504_rate_cap_pct": None,
    }
    fh = tempfile.NamedTemporaryFile("w", delete=False, suffix=".json")
    json.dump(d, fh)
    fh.close()
    return fh.name


# === Structural tests (status-agnostic) ===

def test_packet_exists_and_is_json():
    assert PACKET.exists()
    d = _load()
    assert d["artifact_kind"] == "abhe_v0_per_case_scorer_slicer_approval_packet"
    assert d["schema_version"] == "abhe_v0_per_case_scorer_slicer_approval_packet_v0"


def test_approval_status_is_one_of_valid_set():
    d = _load()
    assert d["approval_status"] in {"draft_pending_signature", "approved", "rejected"}


def test_all_forced_false_fields_are_false():
    """FORCED_FALSE invariants must hold regardless of approval_status."""
    d = _load()
    for k in FORCED_FALSE:
        assert d[k] is False, f"{k}_not_false"


def test_required_stop_loss_present():
    d = _load()
    assert REQUIRED_STOP_LOSS.issubset(set(d["stop_loss"]))


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


# === Signed-state tests (on-disk packet, post-G5) ===

def test_approval_status_after_signing_is_approved():
    d = _load()
    assert d["approval_status"] == "approved"


def test_all_authorization_fields_true_after_signing():
    d = _load()
    for k in AUTH_FIELDS:
        assert d[k] is True, f"{k}_must_be_true_after_signing"


def test_signature_block_filled_with_signed_values():
    d = _load()
    sig = d["signature_block"]
    for f in SIG_FIELDS:
        assert f in sig, f"signature_field_{f}_missing"
    for k in ("signed_by", "signed_at_iso8601_utc", "signed_at_commit_sha"):
        v = sig[k]
        assert isinstance(v, str) and v.strip() not in ("", "<unsigned>"), (
            f"{k}_unsigned_or_empty:{v}"
        )
    assert sig["signed_at_iso8601_utc"].endswith("Z"), "signed_at_iso8601_utc_not_zulu"
    assert len(sig["signed_at_commit_sha"]) >= 7
    assert isinstance(sig["cost_latency_cap_token_budget"], int) and sig["cost_latency_cap_token_budget"] > 0
    assert isinstance(sig["cost_latency_cap_wall_clock_s"], int) and sig["cost_latency_cap_wall_clock_s"] > 0
    assert isinstance(sig["regression_cap_error_class_delta_max_cases"], int) and sig["regression_cap_error_class_delta_max_cases"] > 0
    assert isinstance(sig["cost_amplification_cap_factor"], (int, float)) and sig["cost_amplification_cap_factor"] > 0
    assert isinstance(sig["provider_504_rate_cap_pct"], (int, float)) and sig["provider_504_rate_cap_pct"] > 0


def test_signed_caps_within_user_specified_ranges():
    d = _load()
    sig = d["signature_block"]
    assert sig["cost_latency_cap_token_budget"] <= 5_000_000, "token_budget_too_large_for_bounded_smoke"
    assert sig["cost_latency_cap_wall_clock_s"] <= 7200, "wall_clock_too_large_for_bounded_smoke"
    assert sig["regression_cap_error_class_delta_max_cases"] <= 5
    assert sig["cost_amplification_cap_factor"] <= 10.0
    assert sig["provider_504_rate_cap_pct"] <= 25.0


def test_signed_by_value_documents_delegation():
    """Honest delegation: signed_by must document that this signing was
    performed by the user OR by Claude Code on the user's explicit
    instruction. Either form is acceptable; a literal '<unsigned>' is not."""
    d = _load()
    s = d["signature_block"]["signed_by"]
    assert s != "<unsigned>"
    assert isinstance(s, str) and len(s) > 0


# === Checker behavior tests ===

def test_checker_default_mode_exits_0_on_signed_packet():
    p = _run([sys.executable, str(CHECKER), "--compact"])
    assert p.returncode == 0, f"default mode rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["approval_packet_passed"] is True
    assert out["authorized"] is True
    assert out["approval_status"] == "approved"


def test_checker_strict_mode_exits_0_on_signed_packet():
    p = _run([sys.executable, str(CHECKER), "--compact", "--strict"])
    assert p.returncode == 0, f"strict mode rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["approval_packet_passed"] is True
    assert out["blockers"] == []
    assert out["authorized"] is True


def test_checker_strict_mode_exits_1_on_synthetic_draft():
    """A draft-state tmpfile must still be rejected by strict mode."""
    tmp_path = _make_draft_tmp()
    try:
        p = _run([sys.executable, str(CHECKER), "--packet", tmp_path, "--compact", "--strict"])
        assert p.returncode == 1, f"synthetic-draft strict rc={p.returncode}"
        out = json.loads(p.stdout.strip().splitlines()[-1])
        assert out["approval_packet_passed"] is False
        assert "approval_status_not_approved_in_strict_mode" in out["blockers"]
    finally:
        os.unlink(tmp_path)


def test_checker_rejects_inconsistent_authorized_true_in_draft():
    """Privilege escalation defense: authorized=True while status=draft -> reject."""
    tmp_path = _make_draft_tmp()
    try:
        with open(tmp_path) as fh:
            d = json.load(fh)
        d["authorized"] = True
        with open(tmp_path, "w") as fh:
            json.dump(d, fh)
        p = _run([sys.executable, str(CHECKER), "--packet", tmp_path, "--compact"])
        out = json.loads(p.stdout.strip().splitlines()[-1])
        assert out["approval_packet_passed"] is False
        assert any("authorized_must_be_false_while_draft" in b for b in out["blockers"])
    finally:
        os.unlink(tmp_path)


def test_checker_rejects_forced_false_violation():
    """holdout_authorized=True (or any FORCED_FALSE) must be rejected even
    when signed. Defense against boundary creep."""
    d = _load()
    d["holdout_authorized"] = True  # boundary violation on already-signed packet
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
    d["stop_loss"] = ["raw_leakage"]
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
    d = _load()
    assert d["current_target_unique_scorer_unit_count_pre_slicing"] == 1
    assert d["approved_target_unique_scorer_unit_count_post_slicing"] == 24
