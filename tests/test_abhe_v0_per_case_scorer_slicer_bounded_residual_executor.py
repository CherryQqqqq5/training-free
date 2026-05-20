"""
Boundary tests for G6b-1 per-case scorer slicer executor scaffolding.

Hard contract:
  - dry-run mode emits a strict-schema artifact with all attestations False
  - dry-run validates signed P1.5b packet + slicer manifest
  - dry-run simulates 72 sub-runs with 24 distinct scorer_units per arm
  - dry-run simulates contract_satisfied = True (synthetic)
  - execute mode refuses with NotImplementedError (G6b-1 ships scaffold only)
  - execute mode still reports signed_packet_check passed but called=False
  - no forbidden substring in any non-attestation key
  - module imports only safe stdlib + scripts.* validators
"""
from __future__ import annotations
import ast
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_PYPATH = str(REPO) + ":" + str(REPO / "src")
EXEC = REPO / "scripts/run_abhe_v0_per_case_scorer_slicer_bounded_residual_dev_smoke.py"
RESULT = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_bounded_residual_result.json"

ATTESTATION_MUST_FALSE = [
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called", "runtime_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
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


def test_executor_exists():
    assert EXEC.exists()


def test_dry_run_exit_0_and_writes_artifact():
    p = _run([sys.executable, str(EXEC), "--dry-run", "--write", "--compact"])
    assert p.returncode == 0, f"rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    assert RESULT.exists()


def test_dry_run_artifact_kind_and_mode():
    art = json.loads(RESULT.read_text(encoding="utf-8"))
    assert art["artifact_kind"] == "abhe_v0_per_case_scorer_slicer_bounded_residual_result"
    assert art["schema_version"] == "abhe_v0_per_case_scorer_slicer_bounded_residual_result_v0"
    assert art["execution_mode"] == "dry_run"


def test_dry_run_all_attestations_false():
    art = json.loads(RESULT.read_text(encoding="utf-8"))
    for k in ATTESTATION_MUST_FALSE:
        assert art[k] is False, f"{k}_must_be_false"


def test_dry_run_72_subruns_all_success():
    art = json.loads(RESULT.read_text(encoding="utf-8"))
    assert len(art["per_case_scorer_unit_records"]) == 72
    successes = [r for r in art["per_case_scorer_unit_records"] if r["subrun_status"] == "success"]
    assert len(successes) == 72


def test_dry_run_24_distinct_scorer_units_per_arm():
    art = json.loads(RESULT.read_text(encoding="utf-8"))
    for arm_summary in art["per_arm_summaries"]:
        assert arm_summary["subrun_count_completed"] == 24
        assert arm_summary["scorer_unit_hashes_distinct_count"] == 24
        assert arm_summary["scorer_unit_per_case_unique"] is True


def test_dry_run_three_arms():
    art = json.loads(RESULT.read_text(encoding="utf-8"))
    arms = sorted(a["arm"] for a in art["per_arm_summaries"])
    assert arms == ["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]


def test_dry_run_contract_satisfied_in_simulation():
    """In dry-run (synthetic), the contract is simulated satisfied. This
    tests the orchestration logic — NOT a real measurement."""
    art = json.loads(RESULT.read_text(encoding="utf-8"))
    assert art["score_output_contract_satisfied_for_target"] is True
    assert art["post_slicing_unique_scorer_unit_count_for_target"] == 24
    assert art["post_slicing_compact_to_scorer_unit_factor"] == 1.0


def test_dry_run_caps_all_satisfied():
    art = json.loads(RESULT.read_text(encoding="utf-8"))
    assert art["caps_all_satisfied"] is True
    assert art["stop_loss_triggered"] is False
    assert art["stop_loss_triggers_fired"] == []


def test_dry_run_no_forbidden_substrings():
    art = json.loads(RESULT.read_text(encoding="utf-8"))
    bad = _scan_forbidden(art)
    assert not bad, f"forbidden_substring:{bad}"


def test_dry_run_cumulative_estimates_under_caps():
    art = json.loads(RESULT.read_text(encoding="utf-8"))
    caps = art["caps_from_signed_packet"]
    assert art["cumulative_token_estimate"] <= caps["cost_latency_cap_token_budget"]
    assert art["cumulative_wall_clock_s"] <= caps["cost_latency_cap_wall_clock_s"]


def test_execute_mode_refuses_with_not_implemented():
    p = _run([sys.executable, str(EXEC), "--execute", "--compact"])
    assert p.returncode == 1, f"execute should exit 1; got {p.returncode}\n{p.stdout}\n{p.stderr}"
    out = json.loads(p.stdout.strip())
    assert "execute_blocked_reason" in out
    assert "live_execute_not_yet_wired" in out["execute_blocked_reason"]
    # Critical attestations stay false even when execute attempted
    assert out["provider_calls_made"] is False
    assert out["bfcl_generate_called"] is False
    assert out["bfcl_evaluate_called"] is False
    assert out["scorer_called"] is False
    assert out["performance_evidence"] is False
    # The signed packet + manifest WERE validated (exit 0); only the live
    # wiring path is gated.
    assert out["signed_packet_strict_check_passed"] is True
    assert out["slicer_manifest_strict_check_passed"] is True


def test_executor_rejects_no_mode():
    p = _run([sys.executable, str(EXEC)])
    assert p.returncode == 2
    out = json.loads(p.stdout.strip())
    assert "must_specify_one_of" in out["error"]


def test_executor_rejects_both_modes():
    p = _run([sys.executable, str(EXEC), "--dry-run", "--execute"])
    assert p.returncode == 2
    out = json.loads(p.stdout.strip())
    assert "mutually_exclusive" in out["error"]


def test_module_does_not_import_provider_client_or_bfcl_directly():
    """Static analysis: the executor scaffolding (G6b-1) must NOT yet
    import provider client / BFCL runners. G6b-2 will add those imports
    in a separate commit (and will require extending the blast-radius
    guard list at that time)."""
    tree = ast.parse(EXEC.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
            for n in node.names:
                imports.append((node.module or "") + "." + n.name)
    forbidden = (
        "provider_client", "rashe_source_provider_client",
        "rashe_source_case_provider",
        "bfcl_eval", "bfcl_run",
        "requests", "httpx", "urllib", "openai", "socket",
    )
    for name in imports:
        nl = name.lower()
        for sub in forbidden:
            assert sub not in nl, f"forbidden_import_in_g6b1:{name}_matches_{sub}"


def test_signed_packet_sha256_matches_disk():
    import hashlib
    art = json.loads(RESULT.read_text(encoding="utf-8"))
    pkt = REPO / art["signed_approval_packet_path"]
    expected = "sha256:" + hashlib.sha256(pkt.read_bytes()).hexdigest()
    assert art["signed_approval_packet_sha256"] == expected
