from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

from scripts.check_bfcl_proxy_preflight_failure_telemetry_artifact import (
    check as check_artifact,
    validate as validate_artifact,
)
from scripts.check_bfcl_proxy_preflight_failure_telemetry_gate import (
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check,
    validate_packet,
)
import scripts.run_bfcl_proxy_preflight_failure_telemetry as runner

build_plan = runner.build_plan
execute_proxy_preflight_telemetry = runner.execute_proxy_preflight_telemetry


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _pending_packet(tmp_path: Path) -> Path:
    data = _packet()
    data["approval_status"] = "pending"
    for key in (
        "authorized",
        "provider_request_authorized",
        "proxy_live_preflight_authorized",
        "bfcl_generate_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data[key] = False
    path = tmp_path / "pending_proxy_preflight_telemetry_packet.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _approved_packet(tmp_path: Path) -> Path:
    data = _packet()
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["proxy_live_preflight_authorized"] = True
    for key in (
        "provider_request_authorized",
        "bfcl_generate_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data[key] = False
    path = tmp_path / "approved_proxy_preflight_telemetry_packet.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _write_stage(env: dict, events: list[tuple[str, str]]) -> None:
    stage_path = Path(env["GRC_BASELINE_STAGE_TELEMETRY_PATH"])
    stage_path.parent.mkdir(parents=True, exist_ok=True)
    stage_path.write_text("".join(json.dumps({"stage": stage, "event": event}) + "\n" for stage, event in events), encoding="utf-8")


def _write_success_report(command: list[str]) -> None:
    artifact_dir = Path(command[-1])
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "environment_check": {"is_set": True},
        "passed": True,
        "checks": [
            {"name": "chat_tool_call", "passed": True, "status_code": 200, "request_path_label": "local_proxy_chat_path"},
            {"name": "responses_function_call", "passed": True, "status_code": 200, "request_path_label": "local_proxy_responses_path"},
            {"name": "chat_text_response", "passed": True, "status_code": 200, "request_path_label": "local_proxy_chat_path"},
            {"name": "trace_emission", "passed": True, "status_code": 200, "request_path_label": "local_proxy_responses_path"},
        ],
    }
    (artifact_dir / "preflight_report.json").write_text(json.dumps(report, sort_keys=True), encoding="utf-8")


def _mock_success(command, *, cwd, env, stdout, stderr, check):
    assert env["GRC_BFCL_STOP_AFTER_PREFLIGHT"] == "1"
    assert env["GRC_UPSTREAM_PROFILE"] == "novacode"
    assert env["GRC_UPSTREAM_MODEL"] == "gpt-4.1"
    assert "GRC_BFCL_STOP_AFTER_GENERATE" not in env
    assert command[:4] == ["bash", "-lc", runner._profile_wrapped_command([])[2], "bash"]
    _write_stage(
        env,
        [
            ("validate_model_split", "started"),
            ("validate_model_split", "completed"),
            ("ensure_upstream_auth", "started"),
            ("ensure_upstream_auth", "completed"),
            ("clean_run_state", "started"),
            ("clean_run_state", "completed"),
            ("sync_bfcl_fixture_env", "started"),
            ("sync_bfcl_fixture_env", "completed"),
            ("start_proxy", "started"),
            ("start_proxy", "completed"),
            ("preflight", "started"),
            ("preflight", "completed"),
            ("stop_after_preflight", "started"),
            ("stop_after_preflight", "completed"),
        ],
    )
    _write_success_report(command)
    return subprocess.CompletedProcess(command, 0)


def test_committed_packet_passes_pending_fail_closed() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_proxy_preflight_failure_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["proxy_live_preflight_authorized"] is False
    assert summary["provider_request_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)
    assert summary["performance_evidence"] is False


def test_pending_packet_rejects_authorized_true(tmp_path: Path) -> None:
    data = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    data["authorized"] = True
    blockers = validate_packet(data)
    assert any("authorized_not_false" in blocker for blocker in blockers)
    data = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    data["proxy_live_preflight_authorized"] = True
    blockers = validate_packet(data)
    assert any("proxy_live_preflight_authorized_not_false" in blocker for blocker in blockers)


def test_approved_packet_lifecycle_allows_only_proxy_preflight(tmp_path: Path) -> None:
    summary = check(_approved_packet(tmp_path))
    assert summary["bfcl_proxy_preflight_failure_telemetry_gate_passed"] is True
    assert summary["authorized"] is True
    assert summary["proxy_live_preflight_authorized"] is True
    assert summary["provider_request_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False


def test_rejects_provider_bfcl_scorer_baseline_flags(tmp_path: Path) -> None:
    base = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    for key in (
        "provider_request_authorized",
        "bfcl_generate_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_candidate_and_performance_flags(tmp_path: Path) -> None:
    base = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_wrong_route_missing_fields_and_raw_material() -> None:
    data = _packet()
    data["route_model"] = "gpt-5.2"
    assert any("route" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["allowed_compact_fields"] = [field for field in REQUIRED_COMPACT_FIELDS if field != "provider_call_started"]
    blockers = validate_packet(data)
    assert any("missing_required_compact_fields" in blocker for blocker in blockers)
    assert any("required_preflight_field_missing" in blocker for blocker in blockers)
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["raw_prompt"]
    blockers = validate_packet(data)
    assert any("extra_compact_fields" in blocker or "forbidden_compact_field" in blocker for blocker in blockers)
    data = _packet()
    data["endpoint_value"] = "shape"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))


def test_dry_run_does_not_source_env_read_secrets_or_execute_paths() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["blockers"] == []
    assert plan["env_profile_sourced"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["preflight_command_executed"] is False
    assert plan["live_preflight_executed"] is False
    assert plan["provider_call_started"] is False
    assert plan["bfcl_generate_started"] is False
    assert plan["bfcl_evaluate_started"] is False
    assert plan["scorer_started"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["bfcl_evaluate_executed"] is False
    assert plan["scorer_executed"] is False
    assert plan["full_baseline_executed"] is False
    assert plan["performance_evidence"] is False


def test_dry_run_includes_required_compact_schema() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS
    assert "preflight_exact_exit_code_class" in plan["compact_fields"]
    assert "provider_call_started" in plan["compact_fields"]
    assert "suspected_proxy_preflight_failure_stage" in plan["compact_fields"]


def test_execute_with_pending_packet_fails_closed_before_env_provider_preflight_or_bfcl(tmp_path: Path) -> None:
    def forbidden_run(*args, **kwargs):  # pragma: no cover - should never be called
        raise AssertionError("pending packet reached mocked live command")

    pending = _pending_packet(tmp_path)
    summary = execute_proxy_preflight_telemetry(pending, tmp_path / "telemetry.json", run_command=forbidden_run)
    assert "proxy_preflight_telemetry_packet_not_approved" in summary["blockers"]
    assert summary["env_profile_sourced"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["preflight_command_executed"] is False
    assert summary["live_preflight_executed"] is False
    assert summary["provider_call_started"] is False
    assert summary["bfcl_generate_started"] is False
    assert summary["bfcl_evaluate_started"] is False
    assert summary["scorer_started"] is False
    assert summary["bfcl_generate_executed"] is False
    assert summary["bfcl_evaluate_executed"] is False
    assert summary["scorer_executed"] is False


def test_execute_with_pending_packet_rejects_preexisting_output_before_any_execution(tmp_path: Path) -> None:
    pending = _pending_packet(tmp_path)
    output = tmp_path / "telemetry.json"
    output.write_text("{}", encoding="utf-8")
    summary = execute_proxy_preflight_telemetry(pending, output)
    assert "output_artifact_exists" in summary["blockers"]
    assert summary["preflight_command_executed"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False


def test_approved_execute_path_uses_mocked_preflight_and_writes_compact_artifact(tmp_path: Path) -> None:
    output = tmp_path / "telemetry.json"
    summary = execute_proxy_preflight_telemetry(_approved_packet(tmp_path), output, run_command=_mock_success)
    assert summary["blockers"] == []
    assert summary["preflight_command_executed"] is True
    assert summary["live_preflight_executed"] is True
    assert summary["provider_call_started"] is False
    assert summary["bfcl_generate_started"] is False
    assert summary["bfcl_evaluate_started"] is False
    assert summary["scorer_started"] is False
    assert summary["raw_outputs_removed"] is True
    assert check_artifact(output)["bfcl_proxy_preflight_failure_telemetry_artifact_passed"] is True


def test_provider_call_started_in_mocked_execute_is_stop_gated(tmp_path: Path) -> None:
    def fake_provider_started(command, *, cwd, env, stdout, stderr, check):
        _write_stage(env, [("start_proxy", "started"), ("start_proxy", "completed"), ("preflight", "started"), ("provider_call", "started")])
        _write_success_report(command)
        return subprocess.CompletedProcess(command, 0)

    output = tmp_path / "telemetry.json"
    summary = execute_proxy_preflight_telemetry(_approved_packet(tmp_path), output, run_command=fake_provider_started)
    assert "provider_call_started" in summary["blockers"]
    assert summary["stop_gate_triggered"] == "provider_call_started"
    assert summary["suspected_proxy_preflight_failure_stage"] == "forbidden_provider_call_started"
    assert any("provider_call_started_not_false" in blocker for blocker in check_artifact(output)["blockers"])


def test_artifact_checker_rejects_bfcl_or_scorer_true_and_raw_fields(tmp_path: Path) -> None:
    output = tmp_path / "telemetry.json"
    execute_proxy_preflight_telemetry(_approved_packet(tmp_path), output, run_command=_mock_success)
    data = json.loads(output.read_text(encoding="utf-8"))
    for key in ("bfcl_generate_started", "bfcl_evaluate_started", "scorer_started"):
        mutated = copy.deepcopy(data)
        mutated["records"][0][key] = True
        assert any(key in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["raw_logs"] = "shape"
    assert any("forbidden_key" in blocker or "extra_fields" in blocker for blocker in validate_artifact(mutated))
