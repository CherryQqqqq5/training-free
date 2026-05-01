import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_runtime_behavior_approved import check

SCRIPT = Path("scripts/check_rashe_runtime_behavior_approved.py")
PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_runtime_behavior_approval_packet.json")
CONFIG = Path("configs/runtime_bfcl_skills.yaml")


def copy_inputs(tmp_path: Path) -> tuple[Path, Path]:
    packet = tmp_path / "packet.json"
    config = tmp_path / "runtime_bfcl_skills.yaml"
    shutil.copy(PACKET, packet)
    shutil.copy(CONFIG, config)
    return packet, config


def test_runtime_behavior_approved_checker_compact_passes_current_artifacts():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_runtime_behavior_approved_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["authorized"] is True
    assert summary["runtime_behavior_authorized"] is True
    assert summary["runtime_behavior_scope"] == "synthetic_default_disabled_only"
    assert summary["config_defaults"]["enabled"] is False
    assert summary["downstream_false_fields"]["provider_calls_authorized"] is False
    assert summary["downstream_false_fields"]["source_collection_authorized"] is False
    assert summary["downstream_false_fields"]["candidate_generation_authorized"] is False
    assert summary["downstream_false_fields"]["scorer_authorized"] is False
    assert summary["downstream_false_fields"]["performance_evidence"] is False
    assert summary["downstream_false_fields"]["huawei_acceptance_ready"] is False


def test_fails_if_runtime_packet_is_not_approved(tmp_path):
    packet_path, config_path = copy_inputs(tmp_path)
    packet = json.loads(packet_path.read_text())
    packet["approval_status"] = "pending"
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    summary = check(packet_path, config_path)
    assert summary["rashe_runtime_behavior_approved_passed"] is False
    assert "packet_approval_status_invalid:'pending'" in summary["blockers"]


def test_fails_if_downstream_lane_is_authorized(tmp_path):
    packet_path, config_path = copy_inputs(tmp_path)
    packet = json.loads(packet_path.read_text())
    packet["scorer_authorized"] = True
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    summary = check(packet_path, config_path)
    assert summary["rashe_runtime_behavior_approved_passed"] is False
    assert "packet_downstream_field_not_false:scorer_authorized" in summary["blockers"]


def test_fails_if_no_leakage_flag_is_true(tmp_path):
    packet_path, config_path = copy_inputs(tmp_path)
    packet = json.loads(packet_path.read_text())
    packet["no_leakage_required"]["gold_used"] = True
    packet_path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    summary = check(packet_path, config_path)
    assert summary["rashe_runtime_behavior_approved_passed"] is False
    assert "packet_no_leakage_field_not_false:gold_used" in summary["blockers"]


def test_fails_if_runtime_config_is_enabled(tmp_path):
    packet_path, config_path = copy_inputs(tmp_path)
    config_path.write_text(CONFIG.read_text().replace("enabled: false", "enabled: true", 1))
    summary = check(packet_path, config_path)
    assert summary["rashe_runtime_behavior_approved_passed"] is False
    assert "runtime_config_enabled_not_false" in summary["blockers"]
