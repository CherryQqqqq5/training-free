from __future__ import annotations

import json
from pathlib import Path

from scripts.check_bfcl_live_shape_telemetry_artifact import check as check_artifact
from scripts.check_bfcl_live_shape_telemetry_packet import check as check_packet
from scripts.bfcl_live_shape_telemetry_client import build_signed_live_shape_telemetry_client
from scripts.run_bfcl_live_shape_telemetry import build_plan, execute_telemetry, main as run_main


def _clean_artifact() -> dict[str, object]:
    record = {
        "run_id_label": "web_search_base_0",
        "endpoint_path_label": "responses_to_chat_proxy",
        "request_shape_label": "responses_tools_single_function",
        "response_shape_label": "responses_function_call",
        "status_code_class": "2xx",
        "output_empty": False,
        "tool_call_present": True,
        "parser_decode_path_label": "bfcl_or_openai_responses_decode",
        "token_forwarding_label": "max_output_tokens_forwarded_as_chat_max_tokens",
        "tool_choice_forwarding_label": "function_object",
        "instructions_forwarding_label": "developer_message_prepended",
        "engine_content_empty_label": "content_empty",
        "engine_coercion_label": "not_coerced",
        "raw_text_persisted": False,
        "raw_body_persisted": False,
        "raw_payload_persisted": False,
        "raw_header_persisted": False,
        "raw_log_persisted": False,
        "raw_trace_persisted": False,
        "upstream_returned_tool_call": True,
        "upstream_returned_nonempty_text": False,
        "upstream_returned_true_empty": False,
        "responses_to_chat_conversion_exercised": True,
        "runtime_engine_exercised": True,
        "engine_final_has_tool_calls": True,
        "engine_final_content_empty": True,
        "engine_coerced_nonempty_text_to_empty": False,
        "chat_to_responses_conversion_exercised": True,
        "responses_output_has_function_call": True,
        "responses_output_has_message_text": False,
        "bfcl_or_openai_decode_exercised": True,
        "bfcl_decode_execute_nonempty": True,
        "suspected_failure_stage": "not_reproduced_live_shape_path",
    }
    return {
        "artifact_kind": "bfcl_live_shape_telemetry_compact",
        "active_profile": "novacode",
        "route_model": "gpt-4.1",
        "provider_request_executed": False,
        "bfcl_smoke_executed": False,
        "bfcl_scorer_executed": False,
        "candidate_runtime_activation_authorized": False,
        "performance_evidence": False,
        "sota_3pp_claim_ready": False,
        "huawei_acceptance_ready": False,
        "fallback_allowed": False,
        "gpt_4o_fallback_allowed": False,
        "openrouter_allowed": False,
        "run_ids": ["web_search_base_0", "multi_turn_base_0"],
        "records": [record, {**record, "run_id_label": "multi_turn_base_0"}],
    }


def test_packet_checker_passes_approved_telemetry_only_packet() -> None:
    summary = check_packet()
    assert summary["bfcl_live_shape_telemetry_packet_passed"] is True
    assert summary["planned_run_ids"] == ["web_search_base_0", "multi_turn_base_0"]
    assert summary["live_shape_telemetry_execution_authorized"] is True


def test_runner_dry_run_plan_reads_no_endpoint_or_key_and_calls_no_provider() -> None:
    plan = build_plan()
    assert plan["provider_request_executed"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["bfcl_smoke_executed"] is False
    assert plan["planned_run_id_count"] == 2


def test_runner_execute_mode_fails_closed_without_env_or_client(monkeypatch) -> None:
    for name in ("CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT", "CHUANGZHI_API_KEY", "NOVACODE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert run_main(["--execute-telemetry", "--compact", "--strict"]) == 1


def test_execute_mode_mock_client_writes_clean_artifact_without_raws(tmp_path: Path) -> None:
    def client(request: dict[str, object]) -> list[dict[str, object]]:
        assert request["run_ids"] == ["web_search_base_0", "multi_turn_base_0"]
        return _clean_artifact()["records"]

    out = tmp_path / "telemetry.json"
    summary = execute_telemetry(output=out, client=client, read_env=False)
    assert summary["blockers"] == []
    assert summary["provider_request_executed"] is True
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["diagnostic_written"] is True
    assert check_artifact(out)["bfcl_live_shape_telemetry_artifact_passed"] is True


def test_execute_mode_rejects_wrong_record_count(tmp_path: Path) -> None:
    summary = execute_telemetry(output=tmp_path / "telemetry.json", client=lambda request: [_clean_artifact()["records"][0]], read_env=False)
    assert summary["diagnostic_written"] is False
    assert summary["blockers"] == ["telemetry_record_count_invalid:1"]


def test_artifact_checker_accepts_clean_mock_artifact(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.json"
    path.write_text(json.dumps(_clean_artifact(), indent=2), encoding="utf-8")
    summary = check_artifact(path)
    assert summary["bfcl_live_shape_telemetry_artifact_passed"] is True


def test_artifact_checker_rejects_raw_and_secret_literals(tmp_path: Path) -> None:
    data = _clean_artifact()
    data["records"][0]["raw_payload_persisted"] = True
    data["records"][0]["response_shape_label"] = "https://example.invalid/raw-prompt"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    summary = check_artifact(path)
    assert summary["bfcl_live_shape_telemetry_artifact_passed"] is False
    assert summary["blockers"]


def test_artifact_checker_rejects_route_drift_and_too_many_ids(tmp_path: Path) -> None:
    data = _clean_artifact()
    data["route_model"] = "gpt-4o"
    data["gpt_4o_fallback_allowed"] = True
    data["run_ids"] = ["web_search_base_0", "multi_turn_base_0", "extra"]
    path = tmp_path / "bad_route.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    summary = check_artifact(path)
    assert summary["bfcl_live_shape_telemetry_artifact_passed"] is False
    assert any("route" in blocker or "too_many" in blocker for blocker in summary["blockers"])


class _FakeResponse:
    status = 200

    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.payload = payload if payload is not None else _fake_chat_response("tool_call")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _fake_chat_response(kind: str) -> dict[str, object]:
    if kind == "tool_call":
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "type": "function",
                                "function": {"name": "synthetic_live_shape_telemetry_ping", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ]
        }
    if kind == "text":
        return {"choices": [{"message": {"role": "assistant", "content": "synthetic text", "tool_calls": []}}]}
    if kind == "empty":
        return {}
    if kind == "malformed_nonempty":
        return {"choices": [{"delta": {"content": "synthetic text"}}]}
    raise ValueError(kind)


def _signed_env() -> dict[str, str]:
    return {
        "CHUANGZHI_NOVACODE_ENDPOINT": "https://example.invalid/v1/chat/completions",
        "CHUANGZHI_API_KEY": "fixture-token-not-secret-shaped",
    }


def test_execute_mode_rejects_unsigned_cli_factory_before_env(monkeypatch) -> None:
    for name in ("CHUANGZHI_NOVACODE_ENDPOINT", "NOVACODE_ENDPOINT", "CHUANGZHI_API_KEY", "NOVACODE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert run_main(["--execute-telemetry", "--telemetry-client-factory", "tests.fake:build", "--compact", "--strict"]) == 1


def test_execute_mode_uses_signed_factory_injection(tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def factory(request: dict[str, object]):
        calls.append(request)
        return lambda client_request: _clean_artifact()["records"]

    out = tmp_path / "telemetry.json"
    summary = execute_telemetry(output=out, client_factory=factory, read_env=False)
    assert summary["blockers"] == []
    assert calls and calls[0]["run_ids"] == ["web_search_base_0", "multi_turn_base_0"]
    assert check_artifact(out)["bfcl_live_shape_telemetry_artifact_passed"] is True


def test_signed_transport_factory_mock_opener_returns_compact_records_without_raws() -> None:
    seen_urls: list[str] = []

    def opener(request, timeout):
        seen_urls.append(request.full_url)
        assert timeout == 30
        return _FakeResponse()

    request = {
        "run_ids": ["web_search_base_0", "multi_turn_base_0"],
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "max_total_cases": 2,
        "raw_persistence_authorized": False,
    }
    client = build_signed_live_shape_telemetry_client(request, env=_signed_env(), opener=opener)
    records = client(request)
    assert len(records) == 2
    assert seen_urls == ["https://example.invalid/v1/chat/completions"] * 2
    assert {record["run_id_label"] for record in records} == {"web_search_base_0", "multi_turn_base_0"}
    assert all(record["tool_call_present"] is True for record in records)
    assert all(record["raw_payload_persisted"] is False for record in records)


def test_signed_transport_rejects_id_drift() -> None:
    request = {
        "run_ids": ["web_search_base_0", "unexpected"],
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "max_total_cases": 2,
        "raw_persistence_authorized": False,
    }
    try:
        build_signed_live_shape_telemetry_client(request, env=_signed_env(), opener=lambda request, timeout: _FakeResponse())
    except RuntimeError as exc:
        assert str(exc).startswith("telemetry_run_ids_not_signed")
    else:
        raise AssertionError("expected fail-closed ID drift")


def test_signed_transport_rejects_raw_persistence_flag() -> None:
    request = {
        "run_ids": ["web_search_base_0", "multi_turn_base_0"],
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "max_total_cases": 2,
        "raw_persistence_authorized": True,
    }
    try:
        build_signed_live_shape_telemetry_client(request, env=_signed_env(), opener=lambda request, timeout: _FakeResponse())
    except RuntimeError as exc:
        assert str(exc) == "telemetry_raw_persistence_not_false"
    else:
        raise AssertionError("expected fail-closed raw persistence flag")


def test_signed_transport_rejects_non_https_endpoint() -> None:
    request = {
        "run_ids": ["web_search_base_0", "multi_turn_base_0"],
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "max_total_cases": 2,
        "raw_persistence_authorized": False,
    }
    env = {"CHUANGZHI_NOVACODE_ENDPOINT": "http://example.invalid/v1/chat/completions", "CHUANGZHI_API_KEY": "fixture-token"}
    try:
        build_signed_live_shape_telemetry_client(request, env=env, opener=lambda request, timeout: _FakeResponse())
    except RuntimeError as exc:
        assert str(exc) == "telemetry_endpoint_not_https"
    else:
        raise AssertionError("expected fail-closed non-HTTPS endpoint")



def test_signed_transport_exercises_bfcl_shaped_proxy_runtime_parser_path() -> None:
    seen_payloads: list[dict[str, object]] = []

    def opener(request, timeout):
        payload = json.loads(request.data.decode("utf-8"))
        seen_payloads.append(payload)
        return _FakeResponse(_fake_chat_response("tool_call"))

    request = {
        "run_ids": ["web_search_base_0", "multi_turn_base_0"],
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "max_total_cases": 2,
        "raw_persistence_authorized": False,
    }
    client = build_signed_live_shape_telemetry_client(request, env=_signed_env(), opener=opener)
    records = client(request)
    assert seen_payloads and all("messages" in payload for payload in seen_payloads)
    assert all(payload["messages"][0]["role"] in {"system", "developer"} for payload in seen_payloads)
    assert all(payload.get("tool_choice", {}).get("type") == "function" for payload in seen_payloads)
    assert all(record["responses_to_chat_conversion_exercised"] is True for record in records)
    assert all(record["runtime_engine_exercised"] is True for record in records)
    assert all(record["chat_to_responses_conversion_exercised"] is True for record in records)
    assert all(record["bfcl_or_openai_decode_exercised"] is True for record in records)
    assert all(record["responses_output_has_function_call"] is True for record in records)
    assert all(record["bfcl_decode_execute_nonempty"] is True for record in records)


def test_live_shaped_mock_upstream_classifies_tool_text_empty_and_malformed_distinctly() -> None:
    request = {
        "run_ids": ["web_search_base_0", "multi_turn_base_0"],
        "route_model": "gpt-4.1",
        "active_profile": "novacode",
        "max_total_cases": 2,
        "raw_persistence_authorized": False,
    }

    def run_kind(kind: str) -> dict[str, object]:
        client = build_signed_live_shape_telemetry_client(
            request,
            env=_signed_env(),
            opener=lambda request, timeout: _FakeResponse(_fake_chat_response(kind)),
        )
        return client(request)[0]

    tool = run_kind("tool_call")
    text = run_kind("text")
    empty = run_kind("empty")
    malformed = run_kind("malformed_nonempty")

    assert tool["upstream_returned_tool_call"] is True
    assert tool["responses_output_has_function_call"] is True
    assert text["upstream_returned_nonempty_text"] is True
    assert text["responses_output_has_message_text"] is True
    assert empty["upstream_returned_true_empty"] is True
    assert empty["suspected_failure_stage"] == "true_upstream_empty_response"
    assert malformed["suspected_failure_stage"] == "non_openai_compatible_response_shape"
    assert malformed["upstream_returned_tool_call"] is False
    assert malformed["upstream_returned_nonempty_text"] is False
