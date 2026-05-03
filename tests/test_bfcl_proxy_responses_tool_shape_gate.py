from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_proxy_responses_tool_shape_artifact import check as check_artifact
from scripts.check_bfcl_proxy_responses_tool_shape_artifact import validate as validate_artifact
from scripts.check_bfcl_proxy_responses_tool_shape_gate import (
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check,
    validate_packet,
)
import scripts.run_bfcl_proxy_responses_tool_shape as runner

build_plan = runner.build_plan
execute_proxy_responses_tool_shape = runner.execute_proxy_responses_tool_shape


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _write_packet(tmp_path: Path, data: dict, name: str = "packet.json") -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _approved_packet(tmp_path: Path) -> Path:
    data = _packet()
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["proxy_responses_tool_shape_authorized"] = True
    data["local_proxy_request_authorized"] = True
    data["provider_request_authorized"] = True
    return _write_packet(tmp_path, data, "approved_proxy_responses_tool_shape_packet.json")


def _success_payload() -> dict:
    return {
        "output": [
            {
                "type": "function_call",
                "name": "synthetic_proxy_responses_tool_shape_ping",
                "arguments": "{}",
                "call_id": "synthetic_call",
            }
        ]
    }


def _success_probe(temp_roots: list[Path] | None = None):
    def probe(temp_root: Path):
        if temp_roots is not None:
            temp_roots.append(temp_root)
        (temp_root / "traces").mkdir(parents=True)
        (temp_root / "traces" / "trace.json").write_text("raw trace should be deleted", encoding="utf-8")
        (temp_root / "proxy.log").write_text("raw log should be deleted", encoding="utf-8")
        return {"proxy_started": True, "status": 200, "payload": _success_payload(), "parse_label": "parsed_json", "trace_count": 1}
    return probe



def test_proxy_python_selection_prefers_env_then_repo_venv_then_caller(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GRC_PYTHON", "/tmp/synthetic-python")
    assert runner._select_proxy_python() == ("/tmp/synthetic-python", "grc_python_env")

    monkeypatch.delenv("GRC_PYTHON", raising=False)
    repo = tmp_path / "repo"
    venv_python = repo / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
    venv_python.chmod(0o755)
    monkeypatch.setattr(runner, "REPO_ROOT", repo)
    assert runner._select_proxy_python() == (str(venv_python), "repo_venv")

    no_venv_repo = tmp_path / "repo_without_venv"
    no_venv_repo.mkdir()
    monkeypatch.setattr(runner, "REPO_ROOT", no_venv_repo)
    selected_python, label = runner._select_proxy_python()
    assert selected_python == runner.sys.executable
    assert label == "caller_python"



def test_synthetic_responses_payload_is_direct_chat_aligned() -> None:
    payload = runner._responses_payload()
    assert "instructions" not in payload
    assert payload["temperature"] == 0
    assert payload["max_output_tokens"] == 16
    assert payload["tool_choice"] == {"type": "function", "function": {"name": runner.TOOL_NAME}}
    assert payload["input"] and payload["input"][0]["role"] == "user"



def test_default_proxy_probe_classifies_missing_base_url_before_process_start(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GRC_PYTHON", "/tmp/synthetic-grc-python")
    monkeypatch.delenv("GRC_UPSTREAM_BASE_URL", raising=False)
    monkeypatch.delenv("NOVACODE_BASE_URL", raising=False)

    def forbidden_popen(*args, **kwargs):  # pragma: no cover - must not start proxy
        raise AssertionError("missing base URL should not start proxy")

    monkeypatch.setattr(runner.subprocess, "Popen", forbidden_popen)
    observation = runner._default_proxy_probe(tmp_path)
    assert observation["proxy_started"] is False
    assert observation["proxy_python_label"] == "grc_python_env"
    assert observation["proxy_start_failure_label"] == "proxy_config_startup_failed"
    assert "https://" not in json.dumps(observation, sort_keys=True)


def test_default_proxy_probe_classifies_early_process_exit_without_raw_log(tmp_path: Path, monkeypatch) -> None:
    commands: list[list[str]] = []
    captured_env: dict[str, str] = {}
    monkeypatch.setenv("GRC_PYTHON", "/tmp/synthetic-grc-python")
    monkeypatch.setenv("GRC_UPSTREAM_BASE_URL", "https://provider.invalid/v1")

    class ExitedProcess:
        def poll(self):
            return 1
        def terminate(self):  # pragma: no cover - poll prevents terminate
            raise AssertionError("terminated exited process")
        def wait(self, timeout=None):
            return 1
        def kill(self):  # pragma: no cover
            raise AssertionError("killed exited process")

    def fake_popen(command, **kwargs):
        commands.append(command)
        captured_env.update(kwargs.get("env") or {})
        return ExitedProcess()

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)
    observation = runner._default_proxy_probe(tmp_path)
    assert commands and commands[0][0] == "/tmp/synthetic-grc-python"
    assert observation["proxy_started"] is False
    assert observation["proxy_python_label"] == "grc_python_env"
    assert observation["proxy_start_failure_label"] == "proxy_import_or_process_exit"
    assert observation["proxy_selected_api_key_env_label"] == "CHUANGZHI_API_KEY"
    assert observation["proxy_api_key_env_override_label"] == "approved_chuangzhi_key_env"
    assert "GRC_UPSTREAM_API_KEY_ENV" in captured_env
    assert captured_env["GRC_UPSTREAM_API_KEY_ENV"] == "CHUANGZHI_API_KEY"
    assert captured_env["GRC_PROXY_RESPONSES_TOOL_SHAPE_DIRECT_ALIGNMENT"] == "1"
    assert "raw" not in json.dumps(observation, sort_keys=True)


def test_default_proxy_probe_classifies_health_timeout(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GRC_PYTHON", "/tmp/synthetic-grc-python")
    monkeypatch.setenv("GRC_UPSTREAM_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setattr(runner.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("not ready")))

    class RunningProcess:
        terminated = False
        def poll(self):
            return None
        def terminate(self):
            self.terminated = True
        def wait(self, timeout=None):
            return 0
        def kill(self):  # pragma: no cover
            raise AssertionError("health timeout should terminate cleanly")

    proc = RunningProcess()
    monkeypatch.setattr(runner.subprocess, "Popen", lambda *args, **kwargs: proc)
    observation = runner._default_proxy_probe(tmp_path)
    assert observation["proxy_started"] is False
    assert observation["proxy_python_label"] == "grc_python_env"
    assert observation["proxy_start_failure_label"] == "proxy_health_timeout"
    assert observation["proxy_selected_api_key_env_label"] == "CHUANGZHI_API_KEY"
    assert observation["proxy_api_key_env_override_label"] == "approved_chuangzhi_key_env"
    assert proc.terminated is True


def test_committed_packet_is_pending_and_fail_closed() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_proxy_responses_tool_shape_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["proxy_responses_tool_shape_authorized"] is False
    assert summary["local_proxy_request_authorized"] is False
    assert summary["provider_request_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False
    assert summary["bfcl_evaluate_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["full_baseline_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)


def test_approved_temp_packet_may_flip_only_approval_fields(tmp_path: Path) -> None:
    summary = check(_approved_packet(tmp_path))
    assert summary["bfcl_proxy_responses_tool_shape_gate_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["authorized"] is True
    assert summary["proxy_responses_tool_shape_authorized"] is True
    assert summary["local_proxy_request_authorized"] is True
    assert summary["provider_request_authorized"] is True
    assert summary["bfcl_generate_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False


def test_rejects_partial_or_extra_approval_flips(tmp_path: Path) -> None:
    data = _packet()
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["proxy_responses_tool_shape_authorized"] = True
    data["local_proxy_request_authorized"] = True
    blockers = validate_packet(data)
    assert any("provider_request_authorized_not_true" in blocker for blocker in blockers)

    data = _packet()
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["proxy_responses_tool_shape_authorized"] = True
    data["local_proxy_request_authorized"] = True
    data["provider_request_authorized"] = True
    data["bfcl_generate_authorized"] = True
    blockers = validate_packet(data)
    assert any("bfcl_generate_authorized_not_false" in blocker for blocker in blockers)


def test_rejects_raw_secret_url_and_compact_field_drift() -> None:
    data = _packet()
    data["note"] = "raw response body"
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["note"] = "https://provider.example/full/url"
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["endpoint_value"] = "redacted"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["raw_provider_response"]
    blockers = validate_packet(data)
    assert any("extra_compact_fields" in blocker or "forbidden_compact_field" in blocker for blocker in blockers)


def test_dry_run_does_not_source_profile_or_execute_proxy_provider() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["blockers"] == []
    assert plan["env_profile_sourced"] is False
    assert plan["preflight_command_executed"] is False
    assert plan["proxy_started"] is False
    assert plan["local_proxy_request_executed"] is False
    assert plan["upstream_provider_call_started"] is False
    assert plan["planned_local_request_path_label"] == "local_proxy_responses_path"
    assert plan["planned_upstream_route_label"] == "local_proxy_responses_to_upstream_chat_completions"
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS
    rendered = json.dumps(plan, sort_keys=True)
    assert "/cephfs/qiuyn/.profile" not in rendered
    assert "endpoint_value" not in rendered
    assert "api_key_value" not in rendered
    assert "proxy_selected_api_key_env_label" in rendered
    assert "CHUANGZHI_API_KEY" in rendered


def test_pending_execute_fails_closed_before_proxy_or_provider(tmp_path: Path) -> None:
    def forbidden_probe(temp_root: Path):  # pragma: no cover - must not be called
        raise AssertionError("pending packet reached proxy")

    summary = execute_proxy_responses_tool_shape(DEFAULT_PACKET, tmp_path / "artifact.json", proxy_probe=forbidden_probe)
    assert "proxy_responses_tool_shape_packet_not_approved" in summary["blockers"]
    assert summary["preflight_command_executed"] is False
    assert summary["proxy_started"] is False
    assert summary["local_proxy_request_executed"] is False
    assert summary["upstream_provider_call_started"] is False


def test_output_guard_blocks_before_proxy_or_provider(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    output.write_text("{}", encoding="utf-8")

    def forbidden_probe(temp_root: Path):  # pragma: no cover - must not be called
        raise AssertionError("preexisting artifact reached proxy")

    summary = execute_proxy_responses_tool_shape(_approved_packet(tmp_path), output, proxy_probe=forbidden_probe)
    assert "output_artifact_exists" in summary["blockers"]
    assert summary["proxy_started"] is False


def test_mocked_proxy_success_returns_responses_function_call_labels(tmp_path: Path) -> None:
    temp_roots: list[Path] = []
    output = tmp_path / "artifact.json"
    summary = execute_proxy_responses_tool_shape(_approved_packet(tmp_path), output, proxy_probe=_success_probe(temp_roots))
    assert summary["blockers"] == []
    assert summary["proxy_started"] is True
    assert summary["local_proxy_request_executed"] is True
    assert summary["local_responses_path_selected"] is True
    assert summary["upstream_provider_request_authorized"] is True
    assert summary["upstream_provider_call_started"] is True
    assert summary["upstream_chat_route_label"] == "local_proxy_responses_to_upstream_chat_completions"
    assert summary["http_status_class"] == "2xx"
    assert summary["provider_http_status_label"] == "unknown"
    assert summary["response_body_read"] is True
    assert summary["response_body_persisted"] is False
    assert summary["response_json_parse_label"] == "parsed_json"
    assert summary["responses_envelope_shape_label"] == "responses_function_call"
    assert summary["function_call_present"] is True
    assert summary["function_name_match"] is True
    assert summary["trace_emission_label"] == "trace_emitted"
    assert summary["trace_count_class"] == "one"
    assert summary["proxy_python_label"] in {"grc_python_env", "repo_venv", "caller_python"}
    assert summary["proxy_start_failure_label"] == "none_observed"
    assert summary["proxy_selected_api_key_env_label"] == "CHUANGZHI_API_KEY"
    assert summary["proxy_api_key_env_override_label"] == "approved_chuangzhi_key_env"
    assert summary["raw_temp_outputs_removed"] is True
    assert summary["bfcl_generate_started"] is False
    assert summary["bfcl_evaluate_started"] is False
    assert summary["scorer_started"] is False
    assert summary["full_baseline_executed"] is False
    assert summary["source_collection_executed"] is False
    assert summary["performance_evidence"] is False
    assert check_artifact(output)["bfcl_proxy_responses_tool_shape_artifact_passed"] is True
    assert temp_roots and not temp_roots[0].exists()
    rendered = json.dumps(summary, sort_keys=True) + output.read_text(encoding="utf-8")
    assert "raw trace should be deleted" not in rendered
    assert "raw log should be deleted" not in rendered
    assert "https://" not in rendered
    assert "sk-" not in rendered


def test_malformed_no_output_invalid_json_classify_without_raw_persistence(tmp_path: Path) -> None:
    cases = [
        ("no_output", {"proxy_started": True, "status": 200, "payload": {}, "parse_label": "parsed_json", "trace_count": 1}, "responses_envelope_malformed", "no_output"),
        ("malformed", {"proxy_started": True, "status": 200, "payload": {"output": ["bad"]}, "parse_label": "parsed_json", "trace_count": 1}, "responses_envelope_malformed", "malformed"),
        ("invalid_json", {"proxy_started": True, "status": 200, "payload": {}, "parse_label": "invalid_json", "trace_count": 1}, "responses_envelope_malformed", "invalid_json"),
        ("non_2xx", {"proxy_started": True, "status": 404, "payload": {}, "parse_label": "parsed_json", "trace_count": 1}, "provider_non_2xx", "non_2xx"),
    ]
    for name, observation, blocker, shape in cases:
        output = tmp_path / f"artifact_{name}.json"

        def probe(temp_root: Path, observation=observation):
            return observation

        summary = execute_proxy_responses_tool_shape(_approved_packet(tmp_path), output, proxy_probe=probe)
        assert blocker in summary["blockers"]
        assert summary["responses_envelope_shape_label"] == shape
        assert summary["response_body_persisted"] is False
        assert summary["raw_temp_outputs_removed"] is True
        assert check_artifact(output)["bfcl_proxy_responses_tool_shape_artifact_passed"] is True


def test_artifact_checker_rejects_raw_leaks_and_downstream_flags(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    execute_proxy_responses_tool_shape(_approved_packet(tmp_path), output, proxy_probe=_success_probe())
    data = json.loads(output.read_text(encoding="utf-8"))
    for key in ("bfcl_generate_started", "bfcl_evaluate_started", "scorer_started", "full_baseline_executed", "source_collection_executed", "performance_evidence", "raw_outputs_committed"):
        mutated = copy.deepcopy(data)
        mutated["records"][0][key] = True
        assert any(key in blocker for blocker in validate_artifact(mutated))
    for key in ("raw_response_body", "raw_header", "raw_trace", "prompt_text", "tool_argument_value", "endpoint_value"):
        mutated = copy.deepcopy(data)
        mutated["records"][0][key] = "redacted"
        assert any("forbidden_key" in blocker or "extra_fields" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["note"] = "https://provider.example/raw response body"
    assert any("forbidden_value" in blocker or "extra_fields" in blocker for blocker in validate_artifact(mutated))

    mutated = copy.deepcopy(data)
    mutated["records"][0]["proxy_python_label"] = "python_path_value"
    assert any("proxy_python_label_invalid" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["proxy_start_failure_label"] = "proxy_log_contains_error"
    assert any("proxy_start_failure_label_invalid" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["proxy_selected_api_key_env_label"] = "sk-" + "A" * 32
    assert any("proxy_selected_api_key_env_label_invalid" in blocker or "forbidden_value" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["proxy_api_key_env_override_label"] = "key_value_override"
    assert any("proxy_api_key_env_override_label_invalid" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["raw_temp_outputs_removed"] = False
    assert any("raw_temp_outputs_removed_not_true" in blocker for blocker in validate_artifact(mutated))


def test_runner_source_does_not_source_profile() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "/cephfs/qiuyn/.profile" not in source
    assert "source " not in source


def test_existing_v1_compact_artifact_remains_valid() -> None:
    artifact = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_responses_tool_shape_v1_compact.json")
    if artifact.exists():
        assert check_artifact(artifact)["bfcl_proxy_responses_tool_shape_artifact_passed"] is True
