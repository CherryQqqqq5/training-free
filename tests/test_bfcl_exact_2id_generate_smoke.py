from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_exact_2id_generate_smoke_artifact import check as check_artifact, validate as validate_artifact
from scripts.check_bfcl_exact_2id_smoke_approval_packet import check as check_packet, validate_packet
from scripts.run_bfcl_exact_2id_generate_smoke import (
    SIGNED_IDS,
    _assert_generate_only_command,
    _bfcl_generate_env_summary,
    _bfcl_generate_subprocess_env,
    _generate_command,
    _manifest_payload,
    _manifest_payload_blockers,
    _temporary_bfcl_run_ids_manifest,
    build_plan,
    execute_generate_smoke,
)

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_smoke_approval_packet.json")


def _valid_artifact() -> dict:
    return {
        "artifact_kind": "bfcl_exact_2id_generate_smoke_compact",
        "approval_status": "executed_generate_only",
        "route_profile": "novacode",
        "route_model": "gpt-4.1",
        "provider_profile": "Chuangzhi/Novacode",
        "run_ids": list(SIGNED_IDS),
        "case_count": 2,
        "provider_call_executed": True,
        "bfcl_generate_executed": True,
        "bfcl_evaluate_executed": False,
        "scorer_executed": False,
        "full_baseline_executed": False,
        "candidate_runtime_activation_authorized": False,
        "candidate_jsonl_authorized": False,
        "candidate_pool_ready": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "gpt_5_2_active": False,
        "raw_prompt_persisted": False,
        "raw_case_persisted": False,
        "raw_provider_payload_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "endpoint_or_key_committed": False,
        "records": [
            {
                "run_id": "web_search_base_0",
                "status": "generated",
                "empty_model_response_detected": False,
                "no_tool_text_recorded": False,
                "tool_call_detected": True,
                "protocol_error_detected": False,
                "route_profile": "novacode",
                "route_model": "gpt-4.1",
                "candidate_runtime_activation_authorized": False,
                "candidate_jsonl_authorized": False,
                "candidate_pool_ready": False,
                "bfcl_evaluate_executed": False,
                "scorer_executed": False,
                "full_baseline_executed": False,
                "performance_evidence": False,
                "sota_3pp_claim_ready": False,
                "huawei_acceptance_ready": False,
            },
            {
                "run_id": "multi_turn_base_0",
                "status": "no_tool_text",
                "empty_model_response_detected": False,
                "no_tool_text_recorded": True,
                "tool_call_detected": False,
                "protocol_error_detected": False,
                "route_profile": "novacode",
                "route_model": "gpt-4.1",
                "candidate_runtime_activation_authorized": False,
                "candidate_jsonl_authorized": False,
                "candidate_pool_ready": False,
                "bfcl_evaluate_executed": False,
                "scorer_executed": False,
                "full_baseline_executed": False,
                "performance_evidence": False,
                "sota_3pp_claim_ready": False,
                "huawei_acceptance_ready": False,
            },
        ],
    }


def test_exact_smoke_packet_checker_includes_generate_only_paths() -> None:
    summary = check_packet(PACKET)
    assert summary["bfcl_exact_2id_smoke_approval_packet_passed"] is True
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    assert packet["generate_only_runner_path"] == "scripts/run_bfcl_exact_2id_generate_smoke.py"
    assert packet["compact_artifact_checker_path"] == "scripts/check_bfcl_exact_2id_generate_smoke_artifact.py"
    assert packet["approval_status"] == "approved"
    assert packet["provider_call_authorized"] is True
    assert packet["bfcl_smoke_authorized"] is True
    assert packet["bfcl_generate_authorized"] is True
    assert packet["bfcl_evaluate_authorized"] is False


def test_dry_run_plan_reads_no_endpoint_or_key_and_calls_no_provider() -> None:
    plan = build_plan(PACKET)
    assert plan["provider_call_executed"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["bfcl_evaluate_executed"] is False
    assert plan["scorer_executed"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["run_ids"] == list(SIGNED_IDS)


def test_subprocess_env_bridges_openai_api_key_from_approved_env_when_missing() -> None:
    source = {"CHUANGZHI_API_KEY": "approved_key_value"}
    bridged = _bfcl_generate_subprocess_env(8131, source)
    assert bridged["OPENAI_API_KEY"] == "approved_key_value"
    assert bridged["OPENAI_BASE_URL"] == "http://127.0.0.1:8131/v1"
    assert "OPENAI_API_KEY" not in source


def test_subprocess_env_preserves_existing_openai_api_key_but_forces_base_url() -> None:
    source = {
        "OPENAI_API_KEY": "existing_openai_key",
        "OPENAI_BASE_URL": "http://127.0.0.1:9999/v1",
        "CHUANGZHI_API_KEY": "approved_key_value",
    }
    bridged = _bfcl_generate_subprocess_env(8131, source)
    assert bridged["OPENAI_API_KEY"] == "existing_openai_key"
    assert bridged["OPENAI_BASE_URL"] == "http://127.0.0.1:8131/v1"


def test_subprocess_env_overrides_external_openai_base_url() -> None:
    bridged = _bfcl_generate_subprocess_env(8133, {"OPENAI_BASE_URL": "http://external.invalid/v1"})
    assert bridged["OPENAI_BASE_URL"] == "http://127.0.0.1:8133/v1"


def test_subprocess_env_overrides_wrong_port_local_openai_base_url() -> None:
    bridged = _bfcl_generate_subprocess_env(8134, {"OPENAI_BASE_URL": "http://127.0.0.1:9999/v1"})
    assert bridged["OPENAI_BASE_URL"] == "http://127.0.0.1:8134/v1"


def test_subprocess_env_can_bridge_from_novacode_key() -> None:
    bridged = _bfcl_generate_subprocess_env(8132, {"NOVACODE_API_KEY": "novacode_key_value"})
    assert bridged["OPENAI_API_KEY"] == "novacode_key_value"
    assert bridged["OPENAI_BASE_URL"] == "http://127.0.0.1:8132/v1"


def test_env_summary_contains_presence_flags_not_values() -> None:
    bridged = _bfcl_generate_subprocess_env(8131, {"CHUANGZHI_API_KEY": "approved_key_value"})
    summary = _bfcl_generate_env_summary(bridged)
    assert summary == {
        "openai_api_key_present": True,
        "openai_base_url_present": True,
        "approved_key_env_present": True,
        "approved_endpoint_env_present": False,
    }
    assert "approved_key_value" not in json.dumps(summary)


def test_execute_mode_fails_closed_while_packet_pending(tmp_path: Path) -> None:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    packet["approval_status"] = "pending"
    packet["authorized"] = False
    packet["provider_call_authorized"] = False
    packet["bfcl_smoke_authorized"] = False
    packet["bfcl_generate_authorized"] = False
    pending_packet = tmp_path / "pending_packet.json"
    pending_packet.write_text(json.dumps(packet), encoding="utf-8")
    summary = execute_generate_smoke(output=tmp_path / "out.json", packet_path=pending_packet, run_root=tmp_path / "run")
    assert summary["provider_call_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert summary["bfcl_evaluate_executed"] is False
    assert summary["scorer_executed"] is False
    assert summary["blockers"]
    assert not (tmp_path / "out.json").exists()


def test_generate_only_runner_command_has_no_evaluate_or_scorer(tmp_path: Path) -> None:
    command = _generate_command(tmp_path / "run", 8131, Path("configs/runtime_bfcl_structured.yaml"), Path("rules/baseline_empty"))
    _assert_generate_only_command(command)
    joined = " ".join(command)
    assert " generate " in f" {joined} "
    assert " evaluate " not in f" {joined} "
    assert "aggregate_bfcl_metrics.py" not in joined
    assert "run_bfcl_v4_baseline.sh" not in joined


def test_generate_only_command_scan_rejects_evaluate() -> None:
    try:
        _assert_generate_only_command(["python", "scripts/run_bfcl_cli.py", "evaluate"])
    except RuntimeError as exc:
        assert "forbidden_evaluate_or_scorer_command" in str(exc)
    else:
        raise AssertionError("expected evaluate command rejection")


def test_signed_ids_exactly_enforced_in_packet() -> None:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    packet["signed_run_ids"] = ["web_search_base_0"]
    blockers = validate_packet(packet)
    assert any("signed_run_ids_invalid" in blocker for blocker in blockers)


def test_artifact_checker_accepts_compact_valid_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.json"
    artifact.write_text(json.dumps(_valid_artifact(), indent=2), encoding="utf-8")
    assert check_artifact(artifact)["bfcl_exact_2id_generate_smoke_artifact_passed"] is True


def test_artifact_checker_rejects_extra_ids_and_missing_ids() -> None:
    data = _valid_artifact()
    data["run_ids"] = ["web_search_base_0", "multi_turn_base_0", "extra_0"]
    data["case_count"] = 3
    blockers = validate_artifact(data)
    assert any("run_ids_invalid" in blocker for blocker in blockers)
    assert any("case_count_invalid" in blocker for blocker in blockers)


def test_artifact_checker_rejects_scorer_evaluate_flags() -> None:
    data = _valid_artifact()
    data["bfcl_evaluate_executed"] = True
    data["scorer_executed"] = True
    data["records"][0]["bfcl_evaluate_executed"] = True
    blockers = validate_artifact(data)
    assert any("bfcl_evaluate_executed_not_false" in blocker for blocker in blockers)
    assert any("scorer_executed_not_false" in blocker for blocker in blockers)


def test_artifact_checker_rejects_raw_markers_route_drift_candidate_performance() -> None:
    data = _valid_artifact()
    data["route_model"] = "gpt-4o"
    data["candidate_pool_ready"] = True
    data["performance_evidence"] = True
    data["records"][0]["status"] = "raw prompt leaked"
    blockers = validate_artifact(data)
    assert "route_drift" in blockers
    assert any("candidate_pool_ready_not_false" in blocker for blocker in blockers)
    assert any("performance_evidence_not_false" in blocker for blocker in blockers)
    assert any("forbidden_value" in blocker for blocker in blockers)


def test_artifact_checker_rejects_endpoint_and_key_literals() -> None:
    data = _valid_artifact()
    data["records"][0]["status"] = "https" + "://example.invalid/raw"
    blockers = validate_artifact(data)
    assert any("forbidden_value" in blocker for blocker in blockers)
    data = _valid_artifact()
    data["records"][0]["status"] = "sk-" + "A" * 32
    blockers = validate_artifact(data)
    assert any("key_literal_forbidden" in blocker for blocker in blockers)


def test_manifest_payload_uses_bfcl_category_to_id_schema() -> None:
    assert _manifest_payload() == {
        "web_search_base": ["web_search_base_0"],
        "multi_turn_base": ["multi_turn_base_0"],
    }


def test_manifest_payload_rejects_legacy_test_case_ids_shape() -> None:
    blockers = _manifest_payload_blockers({"test_case_ids": list(SIGNED_IDS)})
    assert "legacy_test_case_ids_key_forbidden" in blockers
    assert any("manifest_schema_or_ids_invalid" in blocker for blocker in blockers)


def test_temporary_manifest_cleanup_removes_new_file(tmp_path: Path) -> None:
    manifest = tmp_path / "test_case_ids_to_generate.json"
    with _temporary_bfcl_run_ids_manifest(manifest) as path:
        assert path == manifest
        assert json.loads(manifest.read_text(encoding="utf-8")) == {
            "web_search_base": ["web_search_base_0"],
            "multi_turn_base": ["multi_turn_base_0"],
        }
    assert not manifest.exists()


def test_temporary_manifest_cleanup_restores_existing_file_on_success(tmp_path: Path) -> None:
    manifest = tmp_path / "test_case_ids_to_generate.json"
    original = {"test_case_ids": ["existing_case"]}
    manifest.write_text(json.dumps(original), encoding="utf-8")
    with _temporary_bfcl_run_ids_manifest(manifest):
        assert json.loads(manifest.read_text(encoding="utf-8")) == {
            "web_search_base": ["web_search_base_0"],
            "multi_turn_base": ["multi_turn_base_0"],
        }
    assert json.loads(manifest.read_text(encoding="utf-8")) == original


def test_temporary_manifest_cleanup_restores_existing_file_on_failure(tmp_path: Path) -> None:
    manifest = tmp_path / "test_case_ids_to_generate.json"
    original = {"test_case_ids": ["existing_case"]}
    manifest.write_text(json.dumps(original), encoding="utf-8")
    try:
        with _temporary_bfcl_run_ids_manifest(manifest):
            assert json.loads(manifest.read_text(encoding="utf-8")) == {
                "web_search_base": ["web_search_base_0"],
                "multi_turn_base": ["multi_turn_base_0"],
            }
            raise RuntimeError("synthetic_failure")
    except RuntimeError:
        pass
    assert json.loads(manifest.read_text(encoding="utf-8")) == original


def test_pending_packet_fails_before_manifest_mutation(tmp_path: Path, monkeypatch) -> None:
    packet = json.loads(PACKET.read_text(encoding="utf-8"))
    packet["approval_status"] = "pending"
    packet["authorized"] = False
    packet["provider_call_authorized"] = False
    packet["bfcl_smoke_authorized"] = False
    packet["bfcl_generate_authorized"] = False
    pending_packet = tmp_path / "pending_packet.json"
    pending_packet.write_text(json.dumps(packet), encoding="utf-8")
    manifest = tmp_path / "should_not_be_touched.json"
    monkeypatch.setattr("scripts.run_bfcl_exact_2id_generate_smoke._bfcl_package_run_ids_path", lambda: manifest)
    summary = execute_generate_smoke(output=tmp_path / "out.json", packet_path=pending_packet, run_root=tmp_path / "run")
    assert summary["blockers"]
    assert not manifest.exists()
