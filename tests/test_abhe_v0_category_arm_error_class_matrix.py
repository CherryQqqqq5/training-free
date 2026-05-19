"""
Boundary tests for P1.5a category-level arm comparison artifact.

Hard contract:
  - schema strict whitelist
  - no forbidden key substrings outside the attestation allowlist
  - error_type_class_per_case_unique consistent with arms data
  - target_per_case_arm_signal_available correctly reflects current data
    (False because category-level aggregation collapses per-case signal)
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_PYPATH = str(REPO) + ":" + str(REPO / "src")
BUILDER = REPO / "scripts/build_abhe_v0_category_arm_error_class_matrix.py"
CHECKER = REPO / "scripts/check_abhe_category_arm_error_signal.py"
OUT = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_category_arm_error_class_matrix.json"

ATTESTATION_KEYS = {
    "scorer_diff_committed","raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed","gold_expected_committed",
    "argument_values_committed","prompt_literal_committed",
}
FORBIDDEN_SUBS = ("prompt","gold","expected","argument_value","raw_response","raw_payload","scorer_diff")

ALLOWED_TOP = {
    "artifact_kind","schema_version","run_scope","bounded_dev_smoke_only","raw_material_absent",
    "performance_evidence","holdout_touched","full_suite_touched","archive_updated",
    "scorer_diff_committed","raw_provider_payload_committed","raw_bfcl_result_tree_committed",
    "gold_expected_committed","argument_values_committed","prompt_literal_committed",
    "source_per_selected_id_matrix_path","source_per_selected_id_matrix_sha256",
    "categories","summary",
}
ALLOWED_CAT = {
    "bfcl_category","selected_case_count","arms","arm_changed_from_baseline",
    "baseline_arm_name","per_case_arm_signal_available",
}
ALLOWED_ARM = {
    "error_type_class","error_type_class_per_case_unique",
    "inherited_not_independent_count","scorer_unit_valid_count",
    "independent_per_case_signal_available",
}

def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO,
                          env={"PYTHONPATH": _PYPATH, "PATH": "/usr/bin:/bin"})

def _run_builder(write):
    cmd = [sys.executable, str(BUILDER), "--compact", "--strict"]
    if write: cmd.append("--write")
    p = _run(cmd)
    assert p.returncode == 0, "builder failed rc=" + str(p.returncode) + "\n" + p.stdout + "\n" + p.stderr
    return json.loads(p.stdout.strip().splitlines()[-1])

def test_builder_emits_compact_summary():
    s = _run_builder(False)
    assert s["abhe_v0_category_arm_error_class_matrix_passed"] is True
    for k in ("total_categories","total_selected_case_count",
              "categories_with_per_case_arm_signal",
              "categories_where_any_arm_changed_vs_baseline",
              "target_category","target_arm_changed_from_baseline",
              "target_per_case_arm_signal_available"):
        assert k in s

def _scan_forbidden(obj, path="$"):
    if isinstance(obj, dict):
        for k,v in obj.items():
            if k not in ATTESTATION_KEYS:
                kl = k.lower()
                for bad in FORBIDDEN_SUBS:
                    assert bad not in kl, "forbidden " + k + " at " + path
            _scan_forbidden(v, path + "." + k)
    elif isinstance(obj, list):
        for i,x in enumerate(obj):
            _scan_forbidden(x, path + "[" + str(i) + "]")

def test_strict_schema_and_no_forbidden_keys():
    _run_builder(True)
    d = json.loads(OUT.read_text())
    extra = set(d.keys()) - ALLOWED_TOP
    assert not extra, extra
    for c in d["categories"]:
        ec = set(c.keys()) - ALLOWED_CAT
        assert not ec, ec
        for arm_name, arm_obj in c["arms"].items():
            ea = set(arm_obj.keys()) - ALLOWED_ARM
            assert not ea, ea
    _scan_forbidden(d)

def test_attestation_flags_all_false():
    if not OUT.exists():
        _run_builder(True)
    d = json.loads(OUT.read_text())
    for k in ("performance_evidence","holdout_touched","full_suite_touched","archive_updated",
              "scorer_diff_committed","raw_provider_payload_committed",
              "raw_bfcl_result_tree_committed","gold_expected_committed",
              "argument_values_committed","prompt_literal_committed"):
        assert d[k] is False, k

def test_target_signal_truthful_to_data():
    if not OUT.exists():
        _run_builder(True)
    d = json.loads(OUT.read_text())
    s = d["summary"]
    target = s["target_category"]
    cat_obj = next(c for c in d["categories"] if c["bfcl_category"] == target)
    for arm_name, arm_obj in cat_obj["arms"].items():
        assert arm_obj["independent_per_case_signal_available"] == (not arm_obj["error_type_class_per_case_unique"])

def test_checker_passes_for_current_artifact():
    if not OUT.exists():
        _run_builder(True)
    p = _run([sys.executable, str(CHECKER), "--compact", "--strict"])
    chk = json.loads(p.stdout.strip().splitlines()[-1])
    assert chk["abhe_category_arm_error_signal_passed"] is True, chk
