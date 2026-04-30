import json
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_offline_scaffold_ready import check

SCRIPT = Path("scripts/check_rashe_offline_scaffold_ready.py")
ACTIVE = Path("outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json")
SCOPE = Path("outputs/artifacts/stage1_bfcl_acceptance/scope_change_approval_rashe.json")
RUNTIME = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_runtime_implementation_authorization.json")


def write_json(path: Path, payload):
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_rashe_offline_scaffold_checker_compact_passes_fail_closed():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_offline_scaffold_ready"] is True
    assert summary["not_bfcl_performance_readiness"] is True
    assert summary["rashe_route_approved"] is True
    assert summary["rashe_runtime_skeleton_passed"] is True
    assert summary["rashe_step_trace_buffer_offline_passed"] is True
    assert summary["rashe_skill_metadata_passed"] is True
    assert summary["rashe_proposer_schema_passed"] is True
    assert summary["rashe_offline_evolution_loop_passed"] is True
    assert summary["runtime_behavior_authorized"] is False
    assert summary["source_collection_authorized"] is False
    assert summary["candidate_generation_authorized"] is False
    assert summary["candidate_pool_ready"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["sota_3pp_claim_ready"] is False
    assert summary["huawei_acceptance_ready"] is False
    assert summary["bfcl_performance_ready"] is False


def test_fails_if_active_index_lacks_rashe_route(tmp_path):
    active = json.loads(ACTIVE.read_text())
    active["active_route"] = "deterministic_legacy"
    path = write_json(tmp_path / "active.json", active)
    summary = check(path, SCOPE, RUNTIME)
    assert summary["rashe_offline_scaffold_ready"] is False
    assert "active_index_rashe_route_missing" in summary["blockers"]


def test_fails_if_forbidden_active_index_flag_true(tmp_path):
    active = json.loads(ACTIVE.read_text())
    active["performance_evidence"] = True
    path = write_json(tmp_path / "active.json", active)
    summary = check(path, SCOPE, RUNTIME)
    assert summary["rashe_offline_scaffold_ready"] is False
    assert "active_index_performance_evidence_true" in summary["blockers"]
    assert summary["performance_evidence"] is False
    assert summary["bfcl_performance_ready"] is False


def test_fails_if_scope_approval_enables_execution(tmp_path):
    scope = json.loads(SCOPE.read_text())
    scope["execution_authorized"] = True
    path = write_json(tmp_path / "scope.json", scope)
    summary = check(ACTIVE, path, RUNTIME)
    assert summary["rashe_offline_scaffold_ready"] is False
    assert "scope_approval_execution_or_acceptance_path_true" in summary["blockers"]


def test_fails_if_runtime_authorization_enables_behavior(tmp_path):
    runtime = json.loads(RUNTIME.read_text())
    runtime["runtime_behavior_authorized"] = True
    path = write_json(tmp_path / "runtime.json", runtime)
    summary = check(ACTIVE, SCOPE, path)
    assert summary["rashe_offline_scaffold_ready"] is False
    assert "runtime_authorization_runtime_behavior_authorized_true" in summary["blockers"]
