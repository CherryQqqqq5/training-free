"""
Boundary tests for P2 runtime_slot_controller_v3 skeleton artifact.

Hard contract:
  - builder is deterministic on fixture (rebuild stable)
  - schema strict whitelist
  - no forbidden key substrings outside attestation allowlist
  - every case's observed decision matches expected_decision_class
  - runtime_wired_into_proxy MUST be False (skeleton-only invariant)
  - every attestation boolean False
  - checker exits 0 only when above holds
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_PYPATH = str(REPO) + ":" + str(REPO / "src")
BUILDER = REPO / "scripts/build_abhe_v0_runtime_slot_controller_v3_skeleton.py"
CHECKER = REPO / "scripts/check_abhe_runtime_slot_controller_v3_skeleton_ready.py"
OUT = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_v3_skeleton.json"
FIXTURE = REPO / "tests/fixtures/abhe_runtime_slot_controller_v3_skeleton/cases.json"

ATTESTATION_KEYS = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "expected_decision_class", "decision_matches_expectation",
    "decisions_matching_expectation",
}
FORBIDDEN_SUBS = ("prompt", "gold", "argument_value",
                  "raw_response", "raw_payload", "scorer_diff")

ALLOWED_TOP = {
    "artifact_kind", "schema_version", "run_scope", "bounded_dev_smoke_only",
    "raw_material_absent",
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called", "runtime_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
    "source_fixture_path", "source_fixture_sha256",
    "cases", "summary", "blockers",
}
ALLOWED_CASE = {
    "case_id_synthetic", "expected_decision_class", "observed_decision_class",
    "decision_matches_expectation",
    "schema_reader_required_arg_count", "schema_reader_required_args",
    "guard_tool_call_valid", "guard_missing_required_args",
    "guard_incompatible_required_args",
    "binder_bindable_count", "binder_bound_slot_sources",
    "binder_ambiguous_slots", "binder_missing_after_bind",
    "binder_entity_ambiguity_detected",
    "planner_lookup_needed_count", "planner_planned_lookup_by_slot",
    "planner_unrecoverable_slots", "planner_ask_or_insufficient_required",
    "would_block_valid_tool_call",
}
ALLOWED_SUMMARY = {
    "total_cases", "decisions_matching_expectation",
    "decisions_by_class", "any_would_block_valid_tool_call",
    "binder_bound_slot_total", "binder_ambiguous_slot_total",
    "planner_lookup_needed_total", "planner_unrecoverable_slot_total",
}

ATTESTATION_MUST_FALSE = [
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called", "runtime_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
]


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO),
                          env={"PYTHONPATH": _PYPATH, "PATH": "/usr/bin:/bin"})


def _run_builder(write):
    cmd = [sys.executable, str(BUILDER), "--compact", "--strict"]
    if write:
        cmd.append("--write")
    p = _run(cmd)
    assert p.returncode == 0, "builder rc=" + str(p.returncode) + "\n" + p.stdout + "\n" + p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])


def _scan_forbidden(obj, path="$"):
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ATTESTATION_KEYS:
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


def test_builder_emits_compact_summary():
    s = _run_builder(False)
    assert s["abhe_v0_runtime_slot_controller_v3_skeleton_passed"] is True
    assert s["total_cases"] == 5
    assert s["decisions_matching_expectation"] == 5
    assert s["runtime_wired_into_proxy"] is False
    assert s["blockers"] == []


def test_builder_writes_artifact_with_strict_schema():
    _run_builder(True)
    assert OUT.exists()
    art = json.loads(OUT.read_text(encoding="utf-8"))
    assert art["artifact_kind"] == "abhe_v0_runtime_slot_controller_v3_skeleton"
    assert art["schema_version"] == "abhe_v0_runtime_slot_controller_v3_skeleton_v0"
    assert set(art.keys()) == ALLOWED_TOP, (
        "unexpected_top_keys:" + str(set(art.keys()) - ALLOWED_TOP)
        + " missing:" + str(ALLOWED_TOP - set(art.keys()))
    )
    for k in ATTESTATION_MUST_FALSE:
        assert art[k] is False, f"{k}_must_be_false"
    assert art["bounded_dev_smoke_only"] is True
    assert art["raw_material_absent"] is True


def test_each_case_uses_only_whitelisted_keys():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    for cr in art["cases"]:
        bad = set(cr.keys()) - ALLOWED_CASE
        assert not bad, f"case_extra_keys:{bad}"
        assert cr["decision_matches_expectation"] is True
        assert cr["would_block_valid_tool_call"] is False


def test_summary_uses_only_whitelisted_keys():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    s = art["summary"]
    assert set(s.keys()) == ALLOWED_SUMMARY
    assert s["total_cases"] == len(art["cases"])
    assert s["decisions_matching_expectation"] == s["total_cases"]
    assert s["any_would_block_valid_tool_call"] is False


def test_no_forbidden_substring_in_keys():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    bad = _scan_forbidden(art)
    assert not bad, f"forbidden_substring_in_keys:{bad}"


def test_decision_distribution_covers_five_classes():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    classes = set(art["summary"]["decisions_by_class"].keys())
    expected_classes = {
        "allow_valid_tool_call",
        "ask_or_insufficient",
        "ask_or_insufficient_due_ambiguity",
        "bind_recovered_slots_then_call",
        "call_prerequisite_lookup",
    }
    assert classes == expected_classes, f"decision_classes:{classes}"


def test_provenance_recorded_in_bind_case():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    bind_case = [c for c in art["cases"]
                 if c["observed_decision_class"] == "bind_recovered_slots_then_call"][0]
    assert bind_case["binder_bindable_count"] == 1
    assert bind_case["binder_bound_slot_sources"].get("party_size") == "prior_tool_observation"


def test_ambiguity_recorded_in_ambiguous_case():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    amb = [c for c in art["cases"]
           if c["observed_decision_class"] == "ask_or_insufficient_due_ambiguity"][0]
    assert amb["binder_entity_ambiguity_detected"] is True
    assert "party_size" in amb["binder_ambiguous_slots"]


def test_planner_records_recoverability_in_lookup_case():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    lk = [c for c in art["cases"]
          if c["observed_decision_class"] == "call_prerequisite_lookup"][0]
    assert lk["planner_lookup_needed_count"] == 1
    assert lk["planner_planned_lookup_by_slot"].get("party_size") == "get_party_size"


def test_checker_exit_0_strict():
    p = _run([sys.executable, str(CHECKER), "--strict"])
    assert p.returncode == 0, "checker rc=" + str(p.returncode) + "\n" + p.stdout + "\n" + p.stderr
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["abhe_v0_runtime_slot_controller_v3_skeleton_ready"] is True
    assert out["runtime_wired_into_proxy"] is False
    assert out["blockers"] == []


def test_fixture_not_raw_material():
    fx = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert fx.get("raw_material_absent") is True
    assert fx.get("prompt_literal_committed") is False
    assert fx.get("gold_expected_committed") is False
