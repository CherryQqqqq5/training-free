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
    mutated["records"][0]["raw_temp_outputs_removed"] = False
    assert any("raw_temp_outputs_removed_not_true" in blocker for blocker in validate_artifact(mutated))


def test_runner_source_does_not_source_profile() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "/cephfs/qiuyn/.profile" not in source
    assert "source " not in source
