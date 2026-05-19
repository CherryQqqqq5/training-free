"""
Boundary tests for P1 score-output-contract adapter.

Hard contract:
  - schema is a strict whitelist (no extra keys)
  - forbidden keys (prompt / gold / expected / argument_value / raw_response /
    raw_payload / scorer_diff) MUST NOT appear anywhere
  - pass_bool MUST be null whenever per_selected_pass_available is False
  - score_output_contract_satisfied_for_target is True iff every target-category
    row has per_selected_pass_available == True via promotion_source ==
    "direct_one_to_one_scorer_unit"
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_PYPATH = str(REPO_ROOT) + ":" + str(REPO_ROOT / "src")
BUILDER   = REPO_ROOT / "scripts/build_abhe_v0_true_per_selected_id_score_adapter.py"
CHECKER   = REPO_ROOT / "scripts/check_abhe_score_output_contract_satisfied.py"

ALLOWED_TOP = {
    "artifact_kind","schema_version","run_scope","bounded_dev_smoke_only","raw_material_absent",
    "performance_evidence","holdout_touched","full_suite_touched","archive_updated",
    "scorer_diff_committed","raw_provider_payload_committed","raw_bfcl_result_tree_committed",
    "gold_expected_committed","argument_values_committed","prompt_literal_committed",
    "source_per_selected_id_matrix_path","source_per_selected_id_matrix_sha256","rows","summary",
}
ALLOWED_ROW = {
    "selected_index","arm","bfcl_category","scorer_unit_hash","case_stable_hash",
    "per_selected_pass_available","pass_bool","promotion_source","promotion_blocker",
}
ATTESTATION_KEYS_ALLOWLIST = {
    "scorer_diff_committed",
    "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed",
    "gold_expected_committed",
    "argument_values_committed",
    "prompt_literal_committed",
}

FORBIDDEN_KEY_SUBSTRINGS = (
    "prompt","gold","expected","argument_value",
    "raw_response","raw_payload","scorer_diff",
)

def _run_builder(write: bool) -> dict:
    cmd = [sys.executable, str(BUILDER), "--compact", "--strict"]
    if write:
        cmd.append("--write")
    p = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT,
                       env={"PYTHONPATH": _PYPATH, "PATH": "/usr/bin:/bin"})
    assert p.returncode == 0, f"builder failed: rc={p.returncode}\nstdout={p.stdout}\nstderr={p.stderr}"
    return json.loads(p.stdout.strip().splitlines()[-1])

def test_builder_runs_and_emits_compact_summary():
    summ = _run_builder(write=False)
    assert summ["abhe_v0_true_per_selected_id_score_adapter_passed"] is True
    for k in ("total_selected_rows","promoted_direct_count","still_inherited_count",
              "ambiguous_many_to_one_count","target_category","target_promoted_direct_count",
              "target_total_count","score_output_contract_satisfied_for_target"):
        assert k in summ, f"missing summary key {k}"

def _scan_forbidden(obj, path="$"):
    if isinstance(obj, dict):
        for k,v in obj.items():
            if k not in ATTESTATION_KEYS_ALLOWLIST:
                kl = k.lower()
                for bad in FORBIDDEN_KEY_SUBSTRINGS:
                    assert bad not in kl, f"forbidden key {k} at {path}"
            _scan_forbidden(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i,x in enumerate(obj):
            _scan_forbidden(x, f"{path}[{i}]")

def test_builder_writes_strict_schema(tmp_path):
    _run_builder(write=True)
    out = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_true_per_selected_id_score_adapter.json"
    assert out.exists()
    d = json.loads(out.read_text())
    extra_top = set(d.keys()) - ALLOWED_TOP
    assert not extra_top, f"unwhitelisted top keys: {extra_top}"
    for r in d["rows"]:
        extra = set(r.keys()) - ALLOWED_ROW
        assert not extra, f"unwhitelisted row keys: {extra}"
        # pass_bool is null whenever per_selected_pass_available is False
        if not r["per_selected_pass_available"]:
            assert r["pass_bool"] is None, "pass_bool MUST be null when per_selected_pass_available is False"
    _scan_forbidden(d)

def test_no_archive_or_holdout_or_full_suite_side_effect():
    out = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_true_per_selected_id_score_adapter.json"
    if not out.exists():
        _run_builder(write=True)
    d = json.loads(out.read_text())
    for k in ("performance_evidence","holdout_touched","full_suite_touched","archive_updated",
              "scorer_diff_committed","raw_provider_payload_committed",
              "raw_bfcl_result_tree_committed","gold_expected_committed",
              "argument_values_committed","prompt_literal_committed"):
        assert d[k] is False, f"{k} must be False at P1"

def test_contract_satisfied_iff_all_target_rows_promoted():
    out = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_true_per_selected_id_score_adapter.json"
    if not out.exists():
        _run_builder(write=True)
    d = json.loads(out.read_text())
    tc = d["summary"]["target_category"]
    target_rows = [r for r in d["rows"] if r["bfcl_category"] == tc]
    if target_rows:
        promoted = all(
            r["per_selected_pass_available"] and r["promotion_source"] == "direct_one_to_one_scorer_unit"
            for r in target_rows
        )
        assert d["summary"]["score_output_contract_satisfied_for_target"] == promoted

def test_checker_aligns_with_adapter_summary():
    out = REPO_ROOT / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_true_per_selected_id_score_adapter.json"
    if not out.exists():
        _run_builder(write=True)
    p = subprocess.run([sys.executable, str(CHECKER), "--compact", "--strict"],
                       capture_output=True, text=True, cwd=REPO_ROOT,
                       env={"PYTHONPATH": _PYPATH, "PATH": "/usr/bin:/bin"})
    chk = json.loads(p.stdout.strip().splitlines()[-1])
    adapter = json.loads(out.read_text())
    assert chk["abhe_score_output_contract_satisfied"] == adapter["summary"]["score_output_contract_satisfied_for_target"]
