import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path("scripts/check_rashe_runtime_authorization.py")


def base_auth():
    return {
        "report_scope": "rashe_runtime_implementation_authorization",
        "authorization_status": "proposed",
        "scope_change_route": "retrieval_augmented_skill_harness_evolution",
        "short_name": "RASHE",
        "runtime_implementation_authorized": False,
        "provider_calls_authorized": False,
        "source_collection_authorized": False,
        "scorer_authorized": False,
        "candidate_generation_authorized": False,
        "performance_evidence": False,
        "active_acceptance_path": False,
        "candidate_pool_ready": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "default_enabled": False,
        "allowed_future_implementation_files_after_approval": [
            "src/grc/skills/schema.py",
            "src/grc/skills/store.py",
            "src/grc/skills/router.py",
            "src/grc/skills/verifier.py",
            "configs/runtime_bfcl_skills.yaml",
            "tests/test_rashe_runtime_*.py",
        ],
        "required_config_defaults_after_approval": {
            "configs/runtime_bfcl_skills.yaml": {
                "enabled": False,
                "provider_calls_authorized": False,
                "scorer_authorized": False,
                "source_collection_authorized": False,
                "candidate_generation_authorized": False,
            }
        },
        "allowed_initial_tests_after_approval": "synthetic tests only initially",
        "forbidden_until_later_execution_approval": [
            "RuleEngine/proxy behavior change",
            "provider calls",
            "BFCL scorer",
            "source collection",
            "candidate JSONL/dev/holdout manifests",
            "skill extraction from BFCL eval cases",
            "prompt injection active in BFCL runtime",
        ],
        "gates_before_runtime_implementation_authorized_true": {
            "v0_offline_checker_passed": True,
            "no_leakage_policy_passed": True,
            "seed_skills_validated": True,
            "router_ambiguity_fail_closed": True,
            "config_default_disabled": True,
            "code_change_plan_reviewed": True,
            "no_provider_scorer_source_paths_touched": True,
        },
        "no_leakage_required": {
            "gold_used": False,
            "expected_used": False,
            "scorer_diff_used": False,
            "candidate_output_used": False,
            "holdout_used": False,
            "raw_trace_committed": False,
        },
    }


def run_checker(tmp_path, auth):
    path = tmp_path / "auth.json"
    path.write_text(json.dumps(auth))
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--authorization", str(path), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_proposed_runtime_authorization_passes_fail_closed(tmp_path):
    result = run_checker(tmp_path, base_auth())
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_runtime_authorization_passed"] is True
    assert summary["authorization_status"] == "proposed"
    assert summary["runtime_implementation_authorized"] is False


def test_runtime_true_fails_closed(tmp_path):
    auth = base_auth()
    auth["runtime_implementation_authorized"] = True
    result = run_checker(tmp_path, auth)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert "runtime_implementation_authorized_not_false" in summary["blockers"]


def test_provider_source_scorer_candidate_flags_fail_closed(tmp_path):
    auth = base_auth()
    auth["provider_calls_authorized"] = True
    auth["source_collection_authorized"] = True
    auth["scorer_authorized"] = True
    auth["candidate_generation_authorized"] = True
    result = run_checker(tmp_path, auth)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    for key in ["provider_calls_authorized", "source_collection_authorized", "scorer_authorized", "candidate_generation_authorized"]:
        assert f"{key}_not_false" in summary["blockers"]


def test_required_future_file_scope_and_forbidden_scope(tmp_path):
    auth = base_auth()
    auth["allowed_future_implementation_files_after_approval"].remove("src/grc/skills/router.py")
    auth["forbidden_until_later_execution_approval"].remove("provider calls")
    result = run_checker(tmp_path, auth)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert any(b.startswith("allowed_future_files_missing:") for b in summary["blockers"])
    assert any(b.startswith("forbidden_scope_missing:") for b in summary["blockers"])


def test_no_leakage_and_default_disabled_required(tmp_path):
    auth = base_auth()
    auth["no_leakage_required"]["gold_used"] = True
    auth["required_config_defaults_after_approval"]["configs/runtime_bfcl_skills.yaml"]["enabled"] = True
    result = run_checker(tmp_path, auth)
    assert result.returncode == 1
    summary = json.loads(result.stdout)
    assert "no_leakage_gold_used_not_false" in summary["blockers"]
    assert "runtime_config_enabled_not_false" in summary["blockers"]
