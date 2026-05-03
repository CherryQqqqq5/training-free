from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_live_provider_preflight_artifact import check as check_artifact
from scripts.check_bfcl_live_provider_preflight_artifact import validate as validate_artifact
from scripts.check_bfcl_live_provider_preflight_gate import (
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check,
    validate_packet,
)
import scripts.run_bfcl_live_provider_preflight as runner

build_plan = runner.build_plan
execute_live_provider_preflight = runner.execute_live_provider_preflight


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
    data["live_provider_preflight_authorized"] = True
    data["provider_request_authorized"] = True
    return _write_packet(tmp_path, data, "approved_live_provider_preflight_packet.json")


def _response_for_payload(payload: dict):
    assert "/cephfs/qiuyn/.profile" not in json.dumps(payload)
    if "input" in payload:
        return {"output": [{"type": "function_call", "name": "synthetic_live_provider_preflight_ping", "arguments": "{}"}]}
    if payload.get("tools"):
        return {"choices": [{"message": {"tool_calls": [{"type": "function", "function": {"name": "synthetic_live_provider_preflight_ping", "arguments": "{}"}}]}}]}
    return {"choices": [{"message": {"content": "PONG"}}]}


def _capturing_success(calls: list[str]):
    def post_json(target_url: str, api_key: str, payload: dict):
        assert api_key == "secret-test-key"
        calls.append(target_url)
        return 200, _response_for_payload(payload)
    return post_json


def test_committed_packet_is_pending_and_fail_closed() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_live_provider_preflight_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["live_provider_preflight_authorized"] is False
    assert summary["provider_request_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False
    assert summary["bfcl_evaluate_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["full_baseline_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)


def test_approved_temp_packet_may_flip_only_live_provider_approval_fields(tmp_path: Path) -> None:
    summary = check(_approved_packet(tmp_path))
    assert summary["bfcl_live_provider_preflight_gate_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["authorized"] is True
    assert summary["live_provider_preflight_authorized"] is True
    assert summary["provider_request_authorized"] is True
    assert summary["bfcl_generate_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["performance_evidence"] is False


def test_rejects_partial_or_extra_approval_flips(tmp_path: Path) -> None:
    data = _packet()
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["live_provider_preflight_authorized"] = True
    blockers = validate_packet(data)
    assert any("provider_request_authorized_not_true" in blocker for blocker in blockers)

    data = _packet()
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["live_provider_preflight_authorized"] = True
    data["provider_request_authorized"] = True
    data["bfcl_generate_authorized"] = True
    blockers = validate_packet(data)
    assert any("bfcl_generate_authorized_not_false" in blocker for blocker in blockers)


def test_rejects_bfcl_candidate_source_performance_and_huawei_flags() -> None:
    base = _packet()
    for key in (
        "bfcl_generate_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "source_collection_authorized",
        "source_diagnostics_authorized",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        assert any(key in blocker for blocker in validate_packet(data))


def test_rejects_raw_secret_endpoint_url_and_compact_field_drift() -> None:
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


def test_dry_run_does_not_source_profile_read_secrets_or_execute_provider() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["blockers"] == []
    assert plan["env_profile_sourced"] is False
    assert plan["preflight_command_executed"] is False
    assert plan["provider_request_executed"] is False
    assert plan["provider_call_started"] is False
    assert plan["endpoint_mode_label"] == "not_selected"
    assert plan["selected_endpoint_env_label"] == "none"
    assert plan["transport_path_join_label"] == "not_reached"
    assert plan["http_status_class"] == "not_observed"
    assert plan["provider_http_status_label"] == "not_observed"
    assert plan["status_classifier_only"] is True
    assert plan["response_body_read"] is False
    summary_text = json.dumps(plan, sort_keys=True)
    assert "endpoint_value_read" not in summary_text
    assert "api_key_value_read" not in summary_text
    assert plan["bfcl_generate_started"] is False
    assert plan["bfcl_evaluate_started"] is False
    assert plan["scorer_started"] is False
    assert plan["full_baseline_executed"] is False
    assert plan["candidate_specs_inert"] is True
    assert plan["performance_evidence"] is False
    assert plan["huawei_acceptance_ready"] is False
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS


def test_pending_execute_fails_closed_before_env_or_provider(tmp_path: Path) -> None:
    def forbidden_post(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("pending packet reached provider transport")

    summary = execute_live_provider_preflight(DEFAULT_PACKET, tmp_path / "artifact.json", environ={}, post_json=forbidden_post)
    assert "live_provider_preflight_packet_not_approved" in summary["blockers"]
    assert summary["preflight_command_executed"] is False
    assert summary["provider_request_executed"] is False
    assert summary["provider_call_started"] is False
    assert summary["provider_http_status_label"] == "not_observed"
    assert summary["status_classifier_only"] is True
    assert summary["response_body_read"] is False
    assert summary["env_profile_sourced"] is False
    assert summary["bfcl_generate_started"] is False
    assert summary["bfcl_evaluate_started"] is False
    assert summary["scorer_started"] is False


def test_approved_execute_missing_env_writes_compact_failure_without_provider(tmp_path: Path) -> None:
    def forbidden_post(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("missing env reached provider transport")

    output = tmp_path / "artifact.json"
    summary = execute_live_provider_preflight(_approved_packet(tmp_path), output, environ={}, post_json=forbidden_post)
    assert summary["blockers"] == ["missing_endpoint_env"]
    assert summary["provider_request_executed"] is False
    assert summary["provider_call_started"] is False
    assert summary["provider_http_status_label"] == "not_observed"
    assert summary["status_classifier_only"] is True
    assert summary["response_body_read"] is False
    artifact_summary = check_artifact(output)
    assert artifact_summary["bfcl_live_provider_preflight_artifact_passed"] is True
    text = output.read_text(encoding="utf-8")
    assert "https://" not in text
    assert "secret-test-key" not in text


def test_approved_execute_base_url_mode_appends_probe_paths(tmp_path: Path) -> None:
    calls: list[str] = []
    env = {"NOVACODE_BASE_URL": "https://provider.invalid/v1", "CHUANGZHI_API_KEY": "secret-test-key"}
    output = tmp_path / "artifact.json"
    summary = execute_live_provider_preflight(_approved_packet(tmp_path), output, environ=env, post_json=_capturing_success(calls))
    assert calls == ["https://provider.invalid/v1/chat/completions"]
    assert summary["blockers"] == []
    assert summary["preflight_command_executed"] is True
    assert summary["provider_request_executed"] is True
    assert summary["provider_call_started"] is True
    assert summary["endpoint_env_present"] is False
    assert summary["base_url_env_present"] is True
    assert summary["api_key_env_present"] is True
    assert summary["https_endpoint_valid"] is True
    assert summary["endpoint_mode_label"] == "base_url"
    assert summary["selected_endpoint_env_label"] == "NOVACODE_BASE_URL"
    assert summary["transport_path_join_label"] == "base_url_chat_completions_appended"
    assert summary["http_status_class"] == "2xx"
    assert summary["provider_http_status_label"] == "unknown"
    assert summary["status_classifier_only"] is True
    assert summary["response_body_read"] is False
    assert summary["auth_status_label"] == "ok"
    assert summary["model_route_label"] == "unknown"
    assert summary["chat_tool_call_label"] == "not_checked"
    assert summary["responses_tool_call_label"] == "not_checked"
    assert summary["chat_text_response_label"] == "not_checked"
    assert summary["bfcl_generate_started"] is False
    assert summary["bfcl_evaluate_started"] is False
    assert summary["scorer_started"] is False
    assert summary["full_baseline_executed"] is False
    assert summary["performance_evidence"] is False
    assert summary["raw_outputs_removed"] is True
    assert summary["raw_outputs_committed"] is False
    assert check_artifact(output)["bfcl_live_provider_preflight_artifact_passed"] is True
    text = output.read_text(encoding="utf-8")
    assert "https://provider.invalid" not in text
    assert "secret-test-key" not in text


def test_approved_execute_grc_base_url_mode_appends_chat_completions_without_extra_v1(tmp_path: Path) -> None:
    calls: list[str] = []
    env = {"GRC_UPSTREAM_BASE_URL": "https://provider.invalid/v1", "CHUANGZHI_API_KEY": "secret-test-key"}
    output = tmp_path / "artifact.json"
    summary = execute_live_provider_preflight(_approved_packet(tmp_path), output, environ=env, post_json=_capturing_success(calls))
    assert calls == ["https://provider.invalid/v1/chat/completions"]
    assert summary["blockers"] == []
    assert summary["endpoint_mode_label"] == "base_url"
    assert summary["selected_endpoint_env_label"] == "GRC_UPSTREAM_BASE_URL"
    assert summary["transport_path_join_label"] == "base_url_chat_completions_appended"
    assert summary["status_classifier_only"] is True
    assert summary["response_body_read"] is False
    assert check_artifact(output)["bfcl_live_provider_preflight_artifact_passed"] is True


def test_approved_execute_full_endpoint_mode_does_not_append_probe_paths(tmp_path: Path) -> None:
    calls: list[str] = []
    env = {"CHUANGZHI_NOVACODE_ENDPOINT": "https://provider.invalid/v1/chat/completions", "CHUANGZHI_API_KEY": "secret-test-key"}
    output = tmp_path / "artifact.json"
    summary = execute_live_provider_preflight(_approved_packet(tmp_path), output, environ=env, post_json=_capturing_success(calls))
    assert calls == ["https://provider.invalid/v1/chat/completions"]
    assert summary["blockers"] == []
    assert summary["endpoint_env_present"] is True
    assert summary["base_url_env_present"] is False
    assert summary["endpoint_mode_label"] == "full_endpoint"
    assert summary["selected_endpoint_env_label"] == "CHUANGZHI_NOVACODE_ENDPOINT"
    assert summary["transport_path_join_label"] == "endpoint_used_as_is"
    assert summary["status_classifier_only"] is True
    assert summary["response_body_read"] is False
    assert check_artifact(output)["bfcl_live_provider_preflight_artifact_passed"] is True
    text = output.read_text(encoding="utf-8")
    assert "https://provider.invalid" not in text
    assert "secret-test-key" not in text



def test_default_transport_does_not_read_2xx_response_body(monkeypatch) -> None:
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):  # pragma: no cover - must not be called
            raise AssertionError("response body was read")

    def fake_urlopen(request, timeout):
        assert timeout == 30
        return FakeResponse()

    monkeypatch.setattr(runner.urllib.request, "urlopen", fake_urlopen)
    status, payload = runner._default_post_json("https://provider.invalid/v1/chat/completions", "secret-test-key", {"model": "gpt-4.1"})
    assert status == 200
    assert payload == {}


def test_output_artifact_exists_blocks_before_provider(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    output.write_text("{}", encoding="utf-8")

    def forbidden_post(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("preexisting artifact reached provider transport")

    summary = execute_live_provider_preflight(_approved_packet(tmp_path), output, environ={}, post_json=forbidden_post)
    assert "output_artifact_exists" in summary["blockers"]
    assert summary["provider_request_executed"] is False


def test_artifact_checker_rejects_raw_material_and_downstream_flags(tmp_path: Path) -> None:
    calls: list[str] = []
    env = {"NOVACODE_BASE_URL": "https://provider.invalid/v1", "CHUANGZHI_API_KEY": "secret-test-key"}
    output = tmp_path / "artifact.json"
    execute_live_provider_preflight(_approved_packet(tmp_path), output, environ=env, post_json=_capturing_success(calls))
    data = json.loads(output.read_text(encoding="utf-8"))
    for key in ("bfcl_generate_started", "bfcl_evaluate_started", "scorer_started", "full_baseline_executed", "performance_evidence", "raw_outputs_committed"):
        mutated = copy.deepcopy(data)
        mutated["records"][0][key] = True
        assert any(key in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["response_body_read"] = True
    assert any("response_body_read_not_false" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["status_classifier_only"] = False
    assert any("status_classifier_only_not_true" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["raw_response_body"] = "shape"
    assert any("forbidden_key" in blocker or "extra_fields" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["status_body"] = "shape"
    assert any("forbidden_key" in blocker or "extra_fields" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["provider_http_status_label"] = "status_418"
    assert any("provider_http_status_label_invalid" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["note"] = "Huawei +3pp performance evidence"
    assert any("forbidden_value" in blocker or "extra_fields" in blocker for blocker in validate_artifact(mutated))


def test_provider_http_status_label_classifies_mocked_statuses(tmp_path: Path) -> None:
    env = {"NOVACODE_BASE_URL": "https://provider.invalid/v1", "CHUANGZHI_API_KEY": "secret-test-key"}
    cases = [
        (400, "status_400", "provider_non_2xx", "unknown"),
        (401, "status_401", "provider_auth_failed", "auth_failed"),
        (403, "status_403", "provider_auth_failed", "auth_failed"),
        (404, "status_404", "provider_non_2xx", "unknown"),
        (405, "status_405", "provider_non_2xx", "unknown"),
        (415, "status_415", "provider_non_2xx", "unknown"),
        (422, "status_422", "provider_non_2xx", "unknown"),
        (429, "status_429", "provider_non_2xx", "unknown"),
        (418, "other_4xx", "provider_non_2xx", "unknown"),
        (500, "status_5xx", "provider_non_2xx", "unknown"),
        (503, "status_5xx", "provider_non_2xx", "unknown"),
    ]
    for status, label, blocker, auth_label in cases:
        def post_json(target_url: str, api_key: str, payload: dict, status=status):
            assert target_url.endswith("/v1/chat/completions")
            assert api_key == "secret-test-key"
            return status, {}

        output = tmp_path / f"artifact_{status}.json"
        summary = execute_live_provider_preflight(_approved_packet(tmp_path), output, environ=env, post_json=post_json)
        assert summary["provider_request_executed"] is True
        assert summary["provider_call_started"] is True
        assert summary["http_status_class"] == ("4xx" if 400 <= status <= 499 else "5xx")
        assert summary["provider_http_status_label"] == label
        assert summary["auth_status_label"] == auth_label
        assert blocker in summary["blockers"]
        artifact_summary = check_artifact(output)
        assert artifact_summary["bfcl_live_provider_preflight_artifact_passed"] is True
        assert artifact_summary["provider_http_status_label"] == label
        text = output.read_text(encoding="utf-8")
        assert "https://provider.invalid" not in text
        assert "secret-test-key" not in text


def test_provider_http_status_label_classifies_transport_exception(tmp_path: Path) -> None:
    env = {"NOVACODE_BASE_URL": "https://provider.invalid/v1", "CHUANGZHI_API_KEY": "secret-test-key"}

    def post_json(target_url: str, api_key: str, payload: dict):
        raise RuntimeError("synthetic transport failure")

    output = tmp_path / "artifact_transport_error.json"
    summary = execute_live_provider_preflight(_approved_packet(tmp_path), output, environ=env, post_json=post_json)
    assert summary["provider_call_started"] is True
    assert summary["provider_request_executed"] is False
    assert summary["http_status_class"] == "transport_error"
    assert summary["provider_http_status_label"] == "transport_error"
    assert "provider_transport_error" in summary["blockers"]
    artifact_summary = check_artifact(output)
    assert artifact_summary["bfcl_live_provider_preflight_artifact_passed"] is True
    assert artifact_summary["provider_http_status_label"] == "transport_error"
