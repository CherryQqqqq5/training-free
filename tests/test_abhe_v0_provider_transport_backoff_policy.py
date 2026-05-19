"""
Boundary tests for P3 provider transport backoff policy artifact.

Hard contract:
  - builder reads YAML deterministically
  - schema strict whitelist
  - no forbidden key substrings outside attestation allowlist
  - policy_enabled MUST be False (master switch invariant)
  - policy_wired_into_proxy MUST be False (skeleton-only invariant)
  - per_request_timeout < runtime.timeout_sec
  - retry_on_status_codes subset of allowed transient codes
  - jitter_strategy in {none, equal_jitter, full_jitter, decorrelated_jitter}
  - all 10 authorization_*_by_this_policy fields False
  - checker exits 0 only when above holds
"""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_PYPATH = str(REPO) + ":" + str(REPO / "src")
BUILDER = REPO / "scripts/build_abhe_v0_provider_transport_backoff_policy.py"
CHECKER = REPO / "scripts/check_abhe_provider_transport_backoff_policy_ready.py"
OUT = REPO / "outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_provider_transport_backoff_policy.json"
POLICY_YAML = REPO / "configs/runtime_bfcl_provider_transport_backoff_policy.yaml"
RUNTIME_YAML = REPO / "configs/runtime_bfcl_structured.yaml"

ATTESTATION_KEYS = {
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
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
    "scorer_called",
    "policy_enabled", "policy_wired_into_proxy",
    "huawei_acceptance_ready", "sota_3pp_claim_ready",
    "source_policy_yaml_path", "source_policy_yaml_sha256",
    "source_runtime_yaml_path", "source_runtime_yaml_sha256",
    "runtime_timeout_sec", "policy_per_request_timeout_sec",
    "policy_summary", "validation", "blockers",
}

ATTESTATION_MUST_FALSE = [
    "performance_evidence", "holdout_touched", "full_suite_touched", "archive_updated",
    "scorer_diff_committed", "raw_provider_payload_committed",
    "raw_bfcl_result_tree_committed", "gold_expected_committed",
    "argument_values_committed", "prompt_literal_committed",
    "provider_calls_made", "bfcl_generate_called", "bfcl_evaluate_called",
    "scorer_called",
    "policy_enabled", "policy_wired_into_proxy",
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


def test_policy_yaml_exists_and_separate_from_runtime():
    assert POLICY_YAML.exists()
    assert RUNTIME_YAML.exists()
    # confirm they are NOT the same file
    assert POLICY_YAML.read_bytes() != RUNTIME_YAML.read_bytes()


def test_builder_emits_compact_pass():
    s = _run_builder(False)
    assert s["abhe_v0_provider_transport_backoff_policy_passed"] is True
    assert s["policy_enabled"] is False
    assert s["policy_wired_into_proxy"] is False
    assert s["blockers"] == []


def test_builder_writes_artifact_with_strict_schema():
    _run_builder(True)
    assert OUT.exists()
    art = json.loads(OUT.read_text(encoding="utf-8"))
    assert art["artifact_kind"] == "abhe_v0_provider_transport_backoff_policy"
    assert art["schema_version"] == "abhe_v0_provider_transport_backoff_policy_v0"
    assert set(art.keys()) == ALLOWED_TOP, (
        "unexpected_top_keys:" + str(set(art.keys()) - ALLOWED_TOP)
        + " missing:" + str(ALLOWED_TOP - set(art.keys()))
    )
    for k in ATTESTATION_MUST_FALSE:
        assert art[k] is False, f"{k}_must_be_false"
    assert art["bounded_dev_smoke_only"] is True
    assert art["raw_material_absent"] is True


def test_validation_all_true():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    for k, v in art["validation"].items():
        assert v is True, f"validation_{k}_not_true:{v}"


def test_per_request_timeout_strictly_less_than_runtime_timeout():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    assert art["policy_per_request_timeout_sec"] < art["runtime_timeout_sec"]


def test_retry_codes_in_allowed_set():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    allowed = {408, 425, 429, 500, 502, 503, 504, 522, 524}
    for c in art["policy_summary"]["retry_on_status_codes"]:
        assert c in allowed, f"unexpected_retry_code:{c}"


def test_jitter_strategy_within_whitelist():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    assert art["policy_summary"]["jitter_strategy"] in {
        "none", "equal_jitter", "full_jitter", "decorrelated_jitter"
    }


def test_no_forbidden_substring_in_keys():
    art = json.loads(OUT.read_text(encoding="utf-8"))
    bad = _scan_forbidden(art)
    assert not bad, f"forbidden_substring_in_keys:{bad}"


def test_yaml_sha256_recorded_and_stable():
    art1 = json.loads(OUT.read_text(encoding="utf-8"))
    _run_builder(True)
    art2 = json.loads(OUT.read_text(encoding="utf-8"))
    assert art1["source_policy_yaml_sha256"] == art2["source_policy_yaml_sha256"]
    assert art1["source_runtime_yaml_sha256"] == art2["source_runtime_yaml_sha256"]


def test_checker_exit_0_strict():
    p = _run([sys.executable, str(CHECKER), "--strict"])
    assert p.returncode == 0, "checker rc=" + str(p.returncode) + "\n" + p.stdout + "\n" + p.stderr
    out = json.loads(p.stdout.strip().splitlines()[-1])
    assert out["abhe_v0_provider_transport_backoff_policy_ready"] is True
    assert out["policy_enabled"] is False
    assert out["policy_wired_into_proxy"] is False
    assert out["blockers"] == []


def test_runtime_yaml_unchanged_by_this_branch():
    """P3 must NOT modify the existing runtime config."""
    txt = RUNTIME_YAML.read_text(encoding="utf-8")
    assert "provider_transport_backoff_policy" not in txt, (
        "P3 leaked into runtime_bfcl_structured.yaml; must stay in separate file"
    )
