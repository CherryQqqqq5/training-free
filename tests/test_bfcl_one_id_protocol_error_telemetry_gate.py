from __future__ import annotations

import copy
import json
import subprocess
from contextlib import nullcontext
from pathlib import Path

from scripts.check_bfcl_one_id_protocol_error_telemetry_gate import (
    REQUIRED_COMPACT_FIELDS,
    SIGNED_ID,
    check,
    validate_packet,
)
from scripts.run_bfcl_one_id_protocol_error_telemetry import (
    SIGNED_CATEGORY,
    SIGNED_ID_MANIFEST,
    _temporary_protocol_error_manifest,
    build_plan,
    execute_one_id_protocol_error_telemetry,
)

PACKET = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_one_id_protocol_error_telemetry_gate_packet.json")


def _packet() -> dict:
    return json.loads(PACKET.read_text(encoding="utf-8"))


def _write_packet(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "packet.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _pending_packet(tmp_path: Path) -> Path:
    data = copy.deepcopy(_packet())
    data["approval_status"] = "pending"
    for key in ("authorized", "provider_request_authorized", "live_protocol_error_telemetry_authorized", "bfcl_generate_authorized"):
        data[key] = False
    return _write_packet(tmp_path, data)


def test_committed_approved_packet_passes_scoped_gate() -> None:
    summary = check(PACKET)
    assert summary["bfcl_one_id_protocol_error_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["provider_request_authorized"] is True
    assert summary["live_protocol_error_telemetry_authorized"] is True
    assert summary["bfcl_generate_authorized"] is True
    assert summary["signed_run_ids"] == [SIGNED_ID]
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)


def test_temp_pending_packet_passes_fail_closed_gate(tmp_path: Path) -> None:
    summary = check(_pending_packet(tmp_path))
    assert summary["bfcl_one_id_protocol_error_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["provider_request_authorized"] is False
    assert summary["live_protocol_error_telemetry_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False


def test_rejects_pending_authorized_true() -> None:
    data = copy.deepcopy(_packet())
    data["approval_status"] = "pending"
    data["authorized"] = True
    data["provider_request_authorized"] = False
    data["live_protocol_error_telemetry_authorized"] = False
    data["bfcl_generate_authorized"] = False
    assert any("authorized_not_false" in blocker for blocker in validate_packet(data))


def test_rejects_wrong_or_multiple_ids() -> None:
    for ids in (["web_search_base_0"], [SIGNED_ID, "web_search_base_0"], []):
        data = _packet()
        data["signed_run_ids"] = list(ids)
        data["max_run_ids"] = len(ids)
        assert any("signed_run_ids_invalid" in blocker or "max_run_ids_invalid" in blocker for blocker in validate_packet(data))


def test_rejects_evaluate_scorer_full_baseline_flags() -> None:
    for key in ("bfcl_smoke_authorized", "bfcl_evaluate_authorized", "scorer_authorized", "full_baseline_authorized"):
        data = _packet()
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_candidate_performance_flags() -> None:
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data = _packet()
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_raw_fields_endpoints_secrets() -> None:
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["raw_" + "provider_response_body"]
    assert any("forbidden_compact_field" in blocker or "extra_compact_fields" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["notes"] = "api " + "key " + "value"
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["notes"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))


def test_rejects_route_fallback_openrouter() -> None:
    for key, value in (("route_model", "gpt-5.2"), ("gpt_4o_fallback_allowed", True), ("openrouter_allowed", True), ("gpt_5_2_active", True)):
        data = copy.deepcopy(_packet())
        data[key] = value
        assert validate_packet(data)


def test_rejects_missing_protocol_error_stage_schema() -> None:
    data = _packet()
    data["allowed_compact_fields"] = [field for field in data["allowed_compact_fields"] if field != "suspected_protocol_error_stage"]
    assert any("suspected_protocol_error_stage_missing" in blocker or "missing_required_compact_fields" in blocker for blocker in validate_packet(data))


def test_dry_run_does_not_read_endpoint_key_or_execute_provider_or_bfcl() -> None:
    plan = build_plan(PACKET)
    assert plan["blockers"] == []
    assert plan["planned_run_ids"] == [SIGNED_ID]
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["provider_request_executed"] is False
    assert plan["live_protocol_error_telemetry_executed"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["bfcl_smoke_executed"] is False
    assert plan["bfcl_evaluate_executed"] is False
    assert plan["scorer_executed"] is False
    assert plan["performance_evidence"] is False
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS


def test_pending_execute_fails_closed_without_endpoint_key_or_execution(tmp_path: Path) -> None:
    summary = execute_one_id_protocol_error_telemetry(_pending_packet(tmp_path), tmp_path / "protocol.json")
    assert "one_id_protocol_error_telemetry_packet_not_approved" in summary["blockers"]
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["provider_request_executed"] is False
    assert summary["bfcl_generate_executed"] is False
    assert not (tmp_path / "protocol.json").exists()


def test_approved_execute_path_with_mocks_cannot_enter_real_provider_or_bfcl(tmp_path: Path, monkeypatch) -> None:
    for name in (
        "CHUANGZHI_NOVACODE_ENDPOINT",
        "NOVACODE_ENDPOINT",
        "NOVACODE_BASE_URL",
        "CHUANGZHI_API_KEY",
        "NOVACODE_API_KEY",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    data = copy.deepcopy(_packet())
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["provider_request_authorized"] = True
    data["live_protocol_error_telemetry_authorized"] = True
    data["bfcl_generate_authorized"] = True
    packet_path = _write_packet(tmp_path, data)
    calls: dict[str, object] = {}

    class FakeProc:
        def terminate(self) -> None:
            calls["terminated"] = True

        def wait(self, timeout: int) -> None:
            calls["wait_timeout"] = timeout

        def kill(self) -> None:
            calls["killed"] = True

    def fake_start_proxy(port, trace_dir, runtime_config, rules_dir, log_path):
        calls["start_proxy"] = {"port": port, "trace_dir": trace_dir.name, "log_name": log_path.name}
        return FakeProc()

    def fake_run_generate(command, env):
        calls["generate_command"] = command
        calls["generate_env_has_decode_capture"] = "GRC_BFCL_DECODE_SHAPE_CAPTURE_PATH" in env
        assert "generate" in command
        assert "evaluate" not in command
        assert SIGNED_CATEGORY in command
        assert "web_search_base" not in command
        result_dir = Path(command[command.index("--result-dir") + 1])
        result_dir.mkdir(parents=True, exist_ok=True)
        (result_dir / "synthetic_protocol.json").write_text(json.dumps({"id": SIGNED_ID, "error": "synthetic_protocol_error"}), encoding="utf-8")
        Path(env["GRC_BFCL_DECODE_SHAPE_CAPTURE_PATH"]).write_text(
            json.dumps({
                "event": "bfcl_decode",
                "bfcl_decode_execute_nonempty": True,
                "bfcl_decode_output_count": 1,
                "bfcl_decode_exception_class": "none",
            }) + "\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0)

    def fake_trace(trace_dir: Path) -> dict:
        return {
            "status_code": 200,
            "raw_response": {"choices": [{"message": {"tool_calls": [{"shape": "present"}], "content": ""}}]},
        }

    output = tmp_path / "protocol.json"
    summary = execute_one_id_protocol_error_telemetry(
        packet_path,
        output,
        tmp_path / "run_root",
        8139,
        start_proxy=fake_start_proxy,
        run_generate=fake_run_generate,
        sync_fixture_env=lambda run_root, port: calls.setdefault("sync_fixture_env", port),
        manifest_context=nullcontext,
        load_trace=fake_trace,
    )
    assert summary["blockers"] == []
    assert summary["provider_request_executed"] is True
    assert summary["bfcl_generate_executed"] is True
    assert summary["bfcl_smoke_executed"] is False
    assert summary["bfcl_evaluate_executed"] is False
    assert summary["scorer_executed"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert calls["generate_env_has_decode_capture"] is True
    artifact = json.loads(output.read_text(encoding="utf-8"))
    record = artifact["records"][0]
    assert artifact["run_ids"] == [SIGNED_ID]
    assert record["provider_response_has_tool_calls"] is True
    assert record["bfcl_decode_execute_nonempty"] is True
    assert record["bfcl_decode_output_count"] == 1
    assert record["classifier_status"] == "protocol_error"
    assert record["compact_result_status"] == "protocol_error"
    assert record["suspected_protocol_error_stage"] == "protocol_status_after_nonempty_decode"
    assert not (tmp_path / "run_root").exists()


def test_temporary_protocol_manifest_uses_signed_schema_and_cleans_up(tmp_path: Path) -> None:
    manifest = tmp_path / "test_case_ids_to_generate.json"
    with _temporary_protocol_error_manifest(manifest):
        assert json.loads(manifest.read_text(encoding="utf-8")) == SIGNED_ID_MANIFEST
    assert not manifest.exists()
