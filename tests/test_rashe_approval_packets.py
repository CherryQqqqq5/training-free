import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_approval_packets import PACKET_STEMS, check

SCRIPT = Path("scripts/check_rashe_approval_packets.py")
BASE = Path("outputs/artifacts/stage1_bfcl_acceptance")


def copy_packets(tmp_path: Path) -> Path:
    for stem in PACKET_STEMS:
        shutil.copy(BASE / f"{stem}.json", tmp_path / f"{stem}.json")
        shutil.copy(BASE / f"{stem}.md", tmp_path / f"{stem}.md")
    return tmp_path


def mutate_packet(base: Path, stem: str, **updates):
    path = base / f"{stem}.json"
    data = json.loads(path.read_text())
    data.update(updates)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def test_rashe_approval_packets_checker_compact_passes_fail_closed():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_approval_packets_passed"] is True
    assert summary["packet_count"] == 5
    assert summary["expected_packet_count"] == 5
    assert summary["authorized_true_count"] == 0
    assert summary["performance_evidence_true_count"] == 0
    assert summary["scorer_authorized_true_count"] == 0
    assert summary["candidate_generation_authorized_true_count"] == 0
    assert summary["huawei_acceptance_ready_true_count"] == 0
    assert summary["runtime_behavior_authorized"] is False
    assert summary["source_collection_authorized"] is False
    assert summary["candidate_pool_ready"] is False


def test_all_packets_have_required_sections_and_pending_status():
    for stem in PACKET_STEMS:
        packet = json.loads((BASE / f"{stem}.json").read_text())
        assert packet["approval_status"] in {"pending", "not_approved"}
        assert packet["authorized"] is False
        assert packet["performance_evidence"] is False
        assert packet["scorer_authorized"] is False
        assert packet["candidate_generation_authorized"] is False
        assert packet["huawei_acceptance_ready"] is False
        for key in ["prerequisites", "allowed_if_approved", "forbidden_until_approved", "rollback_stop_gates"]:
            assert isinstance(packet[key], list)
            assert packet[key]


def test_checker_fails_if_packet_is_approved(tmp_path):
    base = copy_packets(tmp_path)
    mutate_packet(base, "rashe_runtime_behavior_approval_packet", approval_status="approved")
    summary = check(base)
    assert summary["rashe_approval_packets_passed"] is False
    assert "packet_status_not_fail_closed:rashe_runtime_behavior_approval_packet:approved" in summary["blockers"]
    assert "packet_approved:rashe_runtime_behavior_approval_packet" in summary["blockers"]


def test_checker_fails_if_performance_evidence_enabled(tmp_path):
    base = copy_packets(tmp_path)
    mutate_packet(base, "rashe_performance_3pp_huawei_acceptance_approval_packet", performance_evidence=True)
    summary = check(base)
    assert summary["rashe_approval_packets_passed"] is False
    assert summary["performance_evidence_true_count"] == 1
    assert any("performance_evidence" in blocker for blocker in summary["blockers"])


def test_checker_fails_if_candidate_generation_enabled(tmp_path):
    base = copy_packets(tmp_path)
    mutate_packet(base, "rashe_candidate_proposer_execution_approval_packet", candidate_generation_authorized=True)
    summary = check(base)
    assert summary["rashe_approval_packets_passed"] is False
    assert summary["candidate_generation_authorized_true_count"] == 1
    assert any("candidate_generation_authorized" in blocker for blocker in summary["blockers"])


def test_checker_fails_if_no_leakage_field_missing_or_true(tmp_path):
    base = copy_packets(tmp_path)
    path = base / "rashe_source_real_trace_approval_packet.json"
    packet = json.loads(path.read_text())
    packet["no_leakage_required"]["gold_used"] = True
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    summary = check(base)
    assert summary["rashe_approval_packets_passed"] is False
    assert "packet_no_leakage_field_not_false:rashe_source_real_trace_approval_packet:gold_used" in summary["blockers"]
