"""
Boundary tests for G7-revised v2 score adapter.

Hard contract:
  - builder reads on-disk diagnostic (G6b-2 output)
  - emits artifact with strict whitelist schema
  - all 24 multi_turn_miss_param rows promoted
  - target_promoted_direct_count == 24 (was 17 in P1)
  - score_output_contract_satisfied_for_target_v2 == true (was false in P1)
  - 7 passing IDs match the diagnostic
  - 17 failing IDs have error_type_class from BFCL taxonomy
  - no forbidden substring in any non-attestation key
  - all attestation booleans false
  - source_diagnostic_sha256 matches disk
  - checker strict exit 0
"""
from __future__ import annotations
import hashlib, json, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_PYPATH = str(REPO) + ":" + str(REPO / "src")
BUILDER = REPO / "scripts/build_abhe_v0_per_selected_id_score_adapter_v2.py"
CHECKER = REPO / "scripts/check_abhe_v0_per_selected_id_score_adapter_v2_ready.py"
OUT = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_selected_id_score_adapter_v2.json"
DIAGNOSTIC = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_baseline_arm_residual_smoke_per_case_diagnostic.json"

ATTESTATION_MUST_FALSE = [
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "sota_3pp_claim_ready", "huawei_acceptance_ready",
]

ALLOWED_TOP_KEYS = {
    "artifact_kind", "schema_version", "run_scope", "bounded_dev_smoke_only",
    "raw_material_absent",
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "sota_3pp_claim_ready", "huawei_acceptance_ready",
    "source_diagnostic_path", "source_diagnostic_sha256",
    "target_category", "target_arms_in_scope", "target_arms_pending",
    "rows", "summary",
}
ALLOWED_ROW_KEYS = {
    "arm", "bfcl_category", "case_id", "selected_index",
    "per_selected_pass_available", "pass_bool",
    "promotion_source", "promotion_blocker", "error_type_class",
}

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
    if write: cmd.append("--write")
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


def test_builder_emits_compact_pass():
    s = _run_builder(False)
    assert s["abhe_v0_per_selected_id_score_adapter_v2_passed"] is True
    assert s["target_category"] == "multi_turn_miss_param"
    assert s["target_arms_in_scope"] == ["baseline"]


def test_builder_writes_artifact():
    _run_builder(True)
    assert OUT.exists()


def test_artifact_schema_strict():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    assert art["artifact_kind"] == "abhe_v0_per_selected_id_score_adapter_v2"
    assert art["schema_version"] == "abhe_v0_per_selected_id_score_adapter_v2_v0"
    extra = set(art.keys()) - ALLOWED_TOP_KEYS
    assert not extra, f"unexpected_top_keys: {extra}"


def test_all_attestations_false():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    for k in ATTESTATION_MUST_FALSE:
        assert art[k] is False, f"{k}_must_be_false"


def test_24_rows_for_target():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    assert len(art["rows"]) == 24


def test_all_rows_promoted_direct():
    """The headline G7-revised claim: 24/24 promoted directly."""
    art = json.loads(OUT.read_text(encoding="utf-8"))
    for row in art["rows"]:
        assert row["per_selected_pass_available"] is True
        assert row["promotion_source"] == "direct_from_bfcl_score_json_invalid_record_set_diff"
        assert row["promotion_blocker"] is None


def test_summary_contract_satisfied():
    """target_promoted_direct_count = 24/24 (was 17/24 in P1)."""
    art = json.loads(OUT.read_text(encoding="utf-8"))
    s = art["summary"]
    assert s["target_total_count"] == 24
    assert s["target_promoted_direct_count"] == 24
    assert s["target_per_selected_pass_available_count"] == 24
    assert s["score_output_contract_satisfied_for_target_v2"] is True


def test_pass_fail_counts_match_diagnostic():
    diag = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    target_diag = [c for c in diag["per_case_records"] if c["category"] == "multi_turn_miss_param"]
    diag_pass = sum(1 for c in target_diag if c["passed"])
    diag_fail = sum(1 for c in target_diag if not c["passed"])
    art = json.loads(OUT.read_text(encoding="utf-8"))
    assert art["summary"]["target_pass_count"] == diag_pass
    assert art["summary"]["target_fail_count"] == diag_fail
    assert diag_pass + diag_fail == 24


def test_per_row_pass_bool_consistent_with_diagnostic():
    diag = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    diag_pass_map = {c["case_id"]: c["passed"]
                     for c in diag["per_case_records"]
                     if c["category"] == "multi_turn_miss_param"}
    art = json.loads(OUT.read_text(encoding="utf-8"))
    for row in art["rows"]:
        assert row["pass_bool"] == diag_pass_map[row["case_id"]]


def test_per_row_error_type_class_consistent_with_diagnostic():
    diag = json.loads(DIAGNOSTIC.read_text(encoding="utf-8"))
    diag_err_map = {c["case_id"]: c["error_type_class"]
                    for c in diag["per_case_records"]
                    if c["category"] == "multi_turn_miss_param"}
    art = json.loads(OUT.read_text(encoding="utf-8"))
    for row in art["rows"]:
        assert row["error_type_class"] == diag_err_map[row["case_id"]]


def test_row_keys_strict_whitelist():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    for row in art["rows"]:
        extra = set(row.keys()) - ALLOWED_ROW_KEYS
        assert not extra, f"row extra keys: {extra}"


def test_selected_index_sorted_and_dense():
    """selected_index should be 0..23 in numeric case_id order."""
    art = json.loads(OUT.read_text(encoding="utf-8"))
    indices = [r["selected_index"] for r in art["rows"]]
    assert indices == list(range(24))
    # case_ids should be in numeric order
    case_nums = [int(r["case_id"].rsplit("_", 1)[-1]) for r in art["rows"]]
    assert case_nums == sorted(case_nums)


def test_no_forbidden_substrings():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    bad = _scan_forbidden(art)
    assert not bad, f"forbidden substring: {bad}"


def test_source_diagnostic_sha256_matches():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    expected = "sha256:" + hashlib.sha256(DIAGNOSTIC.read_bytes()).hexdigest()
    assert art["source_diagnostic_sha256"] == expected


def test_target_arms_pending_correct():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    assert set(art["target_arms_pending"]) == {"conditional_frozen_v2", "runtime_slot_controller_v2"}


def test_checker_strict_exit_0():
    p = _run([sys.executable, str(CHECKER), "--strict"])
    assert p.returncode == 0, f"checker rc={p.returncode}\n{p.stdout}\n{p.stderr}"
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["abhe_v0_per_selected_id_score_adapter_v2_ready"] is True
    assert out["blockers"] == []


def test_original_p1_artifact_not_modified():
    """Defense: G7-revised must not touch the P1 artifact (preserved as
    evidence of the prior matrix-based approach)."""
    p1 = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_true_per_selected_id_score_adapter.json"
    assert p1.exists()
    p1_data = json.loads(p1.read_text(encoding="utf-8"))
    # P1's contract was unsatisfied in the original artifact (17/24)
    assert p1_data["summary"]["target_promoted_direct_count"] == 17
    assert p1_data["summary"]["score_output_contract_satisfied_for_target"] is False
    assert p1_data["artifact_kind"] == "abhe_v0_true_per_selected_id_score_adapter"
