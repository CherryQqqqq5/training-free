import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_candidate_proposer_approval_packet import check
from scripts.check_rashe_candidate_proposer_ready import check_ready

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_proposer_approval_packet.json")
PACKET_CHECKER = Path("scripts/check_rashe_candidate_proposer_approval_packet.py")
READY_CHECKER = Path("scripts/check_rashe_candidate_proposer_ready.py")


def copy_packet(tmp_path: Path) -> Path:
    packet = tmp_path / "packet.json"
    shutil.copy(PACKET, packet)
    return packet


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_candidate_proposer_packet_checker_passes_current_packet():
    result = subprocess.run([sys.executable, str(PACKET_CHECKER), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_candidate_proposer_approval_packet_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["candidate_proposer_execution_authorized"] is True
    assert summary["bounded_candidate_proposer_execution_authorized"] is True
    assert summary["candidate_generation_authorized"] is False
    assert summary["candidate_jsonl_authorized"] is False
    assert summary["candidate_pool_ready"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["allowed_seed_skills"] == ["bfcl_multi_turn_state_tracking", "bfcl_hallucination_abstain"]


def test_candidate_proposer_ready_checker_passes_bounded_execution_state():
    result = subprocess.run([sys.executable, str(READY_CHECKER), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_candidate_proposer_ready_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["source_diagnostic_total_case_count"] == 160
    assert summary["candidate_proposer_execution_authorized"] is True
    assert summary["candidate_proposer_artifacts_passed"] is True
    assert summary["candidate_generation_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False


def test_packet_rejects_unapproved_or_unbounded_candidate_execution(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["approval_status"] = "pending"
    packet["authorized"] = False
    packet["candidate_proposer_execution_authorized"] = False
    packet["bounded_candidate_proposer_execution_authorized"] = False
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]
    assert "candidate_packet_approval_status_invalid:'pending'" in blockers
    assert "candidate_packet_authorized_not_true:False" in blockers
    assert "candidate_packet_candidate_proposer_execution_authorized_not_true:False" in blockers
    assert "candidate_packet_bounded_candidate_proposer_execution_authorized_not_true:False" in blockers


def test_packet_rejects_downstream_authorization(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["candidate_generation_authorized"] = True
    packet["candidate_jsonl_authorized"] = True
    packet["candidate_pool_ready"] = True
    packet["scorer_authorized"] = True
    packet["performance_evidence"] = True
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]
    assert "candidate_packet_candidate_generation_authorized_not_false:True" in blockers
    assert "candidate_packet_candidate_jsonl_authorized_not_false:True" in blockers
    assert "candidate_packet_candidate_pool_ready_not_false:True" in blockers
    assert "candidate_packet_scorer_authorized_not_false:True" in blockers
    assert "candidate_packet_performance_evidence_not_false:True" in blockers


def test_packet_rejects_skill_drift_and_disallowed_skill_use(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["allowed_seed_skills"] = ["bfcl_web_search_decomposition", "bfcl_multi_turn_state_tracking"]
    packet["disallowed_seed_skills"] = []
    packet["trigger_policy_verifier"]["bfcl_web_search_decomposition"] = {"policy": "not allowed", "verifier": "not allowed"}
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]
    assert any(blocker.startswith("candidate_packet_allowed_seed_skills_invalid") for blocker in blockers)
    assert "candidate_packet_disallowed_seed_skills_invalid:[]" in blockers
    assert "candidate_packet_trigger_policy_verifier_skills_invalid" in blockers
    assert "candidate_packet_disallowed_skill_not_listed:bfcl_web_search_decomposition" in blockers


def test_packet_rejects_source_commit_or_evidence_drift(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["source_diagnostics_commit"] = "not-cc21c96b"
    packet["evidence"]["bfcl_multi_turn_state_tracking"]["required_category_buckets"]["multi_turn_base"]["multi_turn_state_lost"] = 19
    packet["evidence"]["bfcl_hallucination_abstain"]["required_category_buckets"]["irrelevance"]["irrelevant_tool_call"] = 19
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]
    assert "candidate_packet_source_diagnostics_commit_invalid:'not-cc21c96b'" in blockers
    assert "candidate_packet_multi_turn_bucket_missing:multi_turn_base" in blockers
    assert "candidate_packet_irrelevance_bucket_missing" in blockers


def test_packet_rejects_missing_forbidden_boundary(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["forbidden_material"] = []
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]
    assert "candidate_packet_forbidden_boundary_missing:raw trace" in blockers
    assert "candidate_packet_forbidden_boundary_missing:provider request/response" in blockers
    assert "candidate_packet_forbidden_boundary_missing:endpoint/key" in blockers


def test_ready_rejects_pending_packet(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["approval_status"] = "pending"
    write_json(packet_path, packet)

    summary = check_ready(packet_path)
    assert summary["rashe_candidate_proposer_ready_passed"] is False
    assert "candidate_ready_packet_not_approved:'pending'" in summary["blockers"]


def test_scope_doc_contains_required_boundaries():
    text = Path("docs/stage1_rashe_candidate_proposer_scope.md").read_text()
    assert "bfcl_multi_turn_state_tracking" in text
    assert "bfcl_hallucination_abstain" in text
    assert "bfcl_web_search_decomposition" in text
    assert "bounded candidate proposer execution" in text.lower()
    assert "remain unauthorized" in text
    assert "not performance evidence" in text
