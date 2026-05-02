import json
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_provider_transport_approval_packet import check

SCRIPT = Path("scripts/check_rashe_provider_transport_approval_packet.py")
APPROVED_SCRIPT = Path("scripts/check_rashe_provider_transport_approved.py")
PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_provider_transport_approval_packet.json")


def copy_packet(tmp_path: Path) -> Path:
    packet = tmp_path / "packet.json"
    shutil.copy(PACKET, packet)
    return packet


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def test_provider_transport_packet_and_approved_checkers_pass_current_packet():
    for script, key in [
        (SCRIPT, "rashe_provider_transport_approval_packet_passed"),
        (APPROVED_SCRIPT, "rashe_provider_transport_approved_passed"),
    ]:
        result = subprocess.run([sys.executable, str(script), "--compact", "--strict"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        assert result.returncode == 0, result.stdout + result.stderr
        summary = json.loads(result.stdout)
        assert summary[key] is True
        assert summary["approval_status"] == "approved"
        assert summary["provider_transport_authorized"] is True
        assert summary["source_diagnostic_execution_authorized"] is True
        assert summary["provider_calls_authorized"] is True
        assert summary["candidate_generation_authorized"] is False
        assert summary["scorer_authorized"] is False
        assert summary["performance_evidence"] is False
        assert summary["huawei_acceptance_ready"] is False
        assert summary["endpoint_allowed_env_vars"] == ["CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT"]
        assert summary["endpoint_env_only"] is True
        if key == "rashe_provider_transport_approved_passed":
            assert summary["metadata_checker_passed"] is True
            assert summary["source_input_checker_passed"] is True
            assert summary["artifact_boundary_checker_passed"] is True
            assert summary["signed_runner_dry_run_passed"] is True
            command = summary["signed_runner_command"]
            for token in [
                "--provider-profile Chuangzhi/Novacode",
                "--model gpt-4.1",
                "--min-cases-per-category 20",
                "--max-cases-per-category 20",
                "--max-total-cases 160",
                "--source-input-root outputs/artifacts/stage1_bfcl_acceptance/rashe_source_inputs_compact/",
                "--output-root outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/",
                "--schema outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostic_compact.schema.json",
                "--execution-adapter scripts.rashe_source_diagnostic_compact_adapter:run_compact_source_diagnostic",
                "--provider-client-factory scripts.rashe_source_provider_client:build_chuangzhi_novacode_source_provider_client",
                "--source-case-provider scripts.rashe_source_case_provider:build_signed_source_case_provider",
                "--dry-run",
            ]:
                assert token in command


def test_packet_rejects_unsigned_scope_and_downstream_flags(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["provider_profile"] = "Unsigned"
    packet["case_count_per_category"] = 25
    packet["total_case_count"] = 200
    packet["candidate_generation_authorized"] = True
    packet["scorer_authorized"] = True
    packet["performance_evidence"] = True
    packet["huawei_acceptance_ready"] = True
    packet["candidate_call_count"] = 1
    packet["scorer_call_count"] = 1
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]

    assert "packet_provider_profile_invalid:'Unsigned'" in blockers
    assert "packet_case_count_per_category_invalid:25" in blockers
    assert "packet_total_case_count_invalid:200" in blockers
    assert "packet_candidate_generation_authorized_not_false:True" in blockers
    assert "packet_scorer_authorized_not_false:True" in blockers
    assert "packet_performance_evidence_not_false:True" in blockers
    assert "packet_huawei_acceptance_ready_not_false:True" in blockers
    assert "packet_candidate_call_count_not_zero:1" in blockers
    assert "packet_scorer_call_count_not_zero:1" in blockers


def test_packet_rejects_key_policy_raw_paths_and_forbidden_field_drift(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["output_root"] = "outputs/artifacts/stage1_bfcl_acceptance/raw_payload/"
    packet["api_key_policy"]["env_only"] = False
    packet["api_key_policy"]["profile_file_read_authorized"] = True
    packet["transport_output_policy"]["raw_request_persisted"] = True
    packet["transport_output_policy"]["allowed_result_fields"].append("raw_payload")
    packet["forbidden_fields"].remove("case_id")
    packet["no_leakage_required"]["api_key_logged_or_written"] = True
    write_json(packet_path, packet)

    blockers = check(packet_path)["blockers"]

    assert "packet_output_root_invalid:'outputs/artifacts/stage1_bfcl_acceptance/raw_payload/'" in blockers
    assert "packet_output_root_raw_indicator:raw_payload" in blockers
    assert "packet_api_key_env_only_not_true" in blockers
    assert "packet_api_key_policy_not_false:profile_file_read_authorized" in blockers
    assert "packet_transport_output_policy_not_false:raw_request_persisted" in blockers
    assert "packet_transport_allowed_result_fields_invalid" in blockers
    assert "packet_forbidden_field_missing:case_id" in blockers
    assert "packet_no_leakage_field_not_false:api_key_logged_or_written" in blockers


def test_packet_rejects_missing_or_unsigned_endpoint_policy(tmp_path):
    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet.pop("endpoint_policy")
    write_json(packet_path, packet)
    blockers = check(packet_path)["blockers"]
    assert "packet_endpoint_policy_missing" in blockers
    assert "packet_endpoint_env_only_not_true" in blockers

    packet_path = copy_packet(tmp_path)
    packet = load_json(packet_path)
    packet["endpoint_policy"]["allowed_env_vars"] = ["UNSIGNED_ENDPOINT"]
    packet["endpoint_policy"]["https_required"] = False
    packet["endpoint_policy"]["profile_file_read_authorized"] = True
    packet["endpoint_policy"]["hardcoded_endpoint_authorized"] = True
    packet["endpoint_policy"]["endpoint_logging_authorized"] = True
    packet["endpoint_policy"]["endpoint_artifact_write_authorized"] = True
    packet["endpoint_policy"]["raw_path_indicator_allowed"] = True
    packet["endpoint_policy"]["default_endpoint_configured"] = True
    packet["no_leakage_required"]["endpoint_logged_or_written"] = True
    write_json(packet_path, packet)
    blockers = check(packet_path)["blockers"]
    assert "packet_endpoint_allowed_env_vars_invalid" in blockers
    assert "packet_endpoint_https_not_required" in blockers
    assert "packet_endpoint_policy_not_false:profile_file_read_authorized" in blockers
    assert "packet_endpoint_policy_not_false:hardcoded_endpoint_authorized" in blockers
    assert "packet_endpoint_policy_not_false:endpoint_logging_authorized" in blockers
    assert "packet_endpoint_policy_not_false:endpoint_artifact_write_authorized" in blockers
    assert "packet_endpoint_policy_not_false:raw_path_indicator_allowed" in blockers
    assert "packet_endpoint_policy_not_false:default_endpoint_configured" in blockers
    assert "packet_no_leakage_field_not_false:endpoint_logged_or_written" in blockers
