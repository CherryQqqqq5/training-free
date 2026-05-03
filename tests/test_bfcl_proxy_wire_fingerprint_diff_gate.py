from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_proxy_wire_fingerprint_diff_artifact import check as check_artifact
from scripts.check_bfcl_proxy_wire_fingerprint_diff_artifact import validate as validate_artifact
from scripts.check_bfcl_proxy_wire_fingerprint_diff_gate import (
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check,
    validate_packet,
)
import scripts.run_bfcl_proxy_wire_fingerprint_diff as runner

build_plan = runner.build_plan
execute_wire_fingerprint_diff = runner.execute_wire_fingerprint_diff


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
    return _write_packet(tmp_path, data, "approved_proxy_wire_fingerprint_diff_packet.json")


def test_committed_packet_is_pending_and_fail_closed() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_proxy_wire_fingerprint_diff_gate_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["authorized"] is False
    assert summary["provider_request_authorized"] is False
    assert summary["proxy_live_request_authorized"] is False
    assert summary["profile_source_authorized"] is False
    assert summary["bfcl_generate_authorized"] is False
    assert summary["bfcl_evaluate_authorized"] is False
    assert summary["scorer_authorized"] is False
    assert summary["full_baseline_authorized"] is False
    assert summary["performance_evidence"] is False
    assert summary["huawei_acceptance_ready"] is False
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)


def test_approved_packet_flips_only_authorized(tmp_path: Path) -> None:
    summary = check(_approved_packet(tmp_path))
    assert summary["bfcl_proxy_wire_fingerprint_diff_gate_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["authorized"] is True
    assert summary["provider_request_authorized"] is False
    assert summary["proxy_live_request_authorized"] is False
    assert summary["profile_source_authorized"] is False

    data = _packet()
    data["approval_status"] = "approved"
    blockers = validate_packet(data)
    assert any("authorized_not_true" in blocker for blocker in blockers)

    data = _packet()
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["provider_request_authorized"] = True
    blockers = validate_packet(data)
    assert any("provider_request_authorized_not_false" in blocker for blocker in blockers)


def test_dry_run_does_not_source_profile_or_call_provider() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["blockers"] == []
    assert plan["preflight_command_executed"] is False
    assert plan["provider_call_started"] is False
    assert plan["proxy_live_request_started"] is False
    assert plan["profile_sourced"] is False
    assert plan["fake_transport_capture_used"] is False
    assert plan["prepared_request_capture_used"] is False
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS
    rendered = json.dumps(plan, sort_keys=True)
    assert "/cephfs/qiuyn/.profile" not in rendered
    assert "https://" not in rendered
    assert "sk-" not in rendered
    assert "Bearer" not in rendered


def test_pending_execute_fails_closed_before_artifact(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    summary = execute_wire_fingerprint_diff(DEFAULT_PACKET, output)
    assert "wire_fingerprint_diff_packet_not_approved" in summary["blockers"]
    assert summary["preflight_command_executed"] is False
    assert summary["provider_call_started"] is False
    assert summary["proxy_live_request_started"] is False
    assert summary["profile_sourced"] is False
    assert summary["fake_transport_capture_used"] is False
    assert summary["prepared_request_capture_used"] is False
    assert not output.exists()


def test_output_guard_blocks_before_artifact_rewrite(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    output.write_text("{}", encoding="utf-8")
    summary = execute_wire_fingerprint_diff(_approved_packet(tmp_path), output)
    assert "output_artifact_exists" in summary["blockers"]
    assert summary["preflight_command_executed"] is False
    assert summary["provider_call_started"] is False
    assert summary["proxy_live_request_started"] is False
    assert output.read_text(encoding="utf-8") == "{}"


def test_execute_prepared_request_capture_labels_proxy_vs_direct(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    summary = execute_wire_fingerprint_diff(_approved_packet(tmp_path), output)
    assert summary["blockers"] == []
    assert summary["provider_call_started"] is False
    assert summary["profile_sourced"] is False
    assert summary["proxy_live_request_started"] is False
    assert summary["fake_transport_capture_used"] is True
    assert summary["prepared_request_capture_used"] is True
    assert summary["raw_outputs_committed"] is False
    assert summary["raw_temp_outputs_removed"] is True
    assert summary["direct_client_stack_label"] == "urllib_request"
    assert summary["proxy_client_stack_label"] == "httpx_async_client"
    assert summary["method_label"] == "post"
    assert summary["url_suffix_label"] == "chat_completions_suffix"
    assert summary["wire_request_target_label"] == "chat_completions_target"
    assert summary["direct_header_name_set_label"] == "authorization_content_type_only"
    assert summary["header_name_set_label"] == "authorization_content_type_content_length_httpx_defaults"
    assert summary["default_header_shape_label"] == "proxy_httpx_defaults_present_direct_not_observed"
    assert summary["wire_user_agent_label"] == "proxy_present_direct_not_observed"
    assert summary["wire_accept_label"] == "proxy_present_direct_not_observed"
    assert summary["wire_accept_encoding_label"] == "proxy_present_direct_not_observed"
    assert summary["wire_connection_label"] == "proxy_present_direct_not_observed"
    assert summary["content_length_shape_label"] == "both_nonzero"
    assert summary["transfer_encoding_label"] == "absent"
    assert summary["body_bytes_shape_match_label"] == "both_compact_json_nonzero"
    assert summary["proxy_env_presence_label"] in {"proxy_env_names_present", "proxy_env_names_absent"}
    assert summary["trust_env_label"] == "true"
    assert summary["http2_config_label"] == "false"
    assert summary["timeout_shape_label"] == "proxy_config_timeout_direct_urllib_timeout"
    assert summary["tls_context_source_label"] == "not_observed"
    assert summary["suspected_403_cause_label"] == "httpx_default_header_context_diff"
    assert summary["bfcl_generate_started"] is False
    assert summary["bfcl_evaluate_started"] is False
    assert summary["scorer_started"] is False
    assert summary["full_baseline_executed"] is False
    assert summary["candidate_specs_inert"] is True
    assert summary["source_collection_executed"] is False
    assert summary["performance_evidence"] is False
    artifact_summary = check_artifact(output)
    assert artifact_summary["bfcl_proxy_wire_fingerprint_diff_artifact_passed"] is True
    rendered = json.dumps(summary, sort_keys=True) + output.read_text(encoding="utf-8")
    assert "https://" not in rendered
    assert "sk-" not in rendered
    assert "Bearer" not in rendered
    assert "synthetic-direct-token" not in rendered
    assert "synthetic-proxy-token" not in rendered
    assert "raw request" not in rendered.lower()
    assert "raw response" not in rendered.lower()


def test_artifact_checker_rejects_raw_leaks_and_downstream_flags(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    execute_wire_fingerprint_diff(_approved_packet(tmp_path), output)
    data = json.loads(output.read_text(encoding="utf-8"))
    for key in (
        "provider_call_started", "profile_sourced", "proxy_live_request_started", "bfcl_generate_started",
        "bfcl_evaluate_started", "scorer_started", "full_baseline_executed", "source_collection_executed",
        "performance_evidence", "raw_outputs_committed",
    ):
        mutated = copy.deepcopy(data)
        mutated["records"][0][key] = True
        assert any(key in blocker for blocker in validate_artifact(mutated))
    for key in ("raw_request_json", "raw_header", "raw_body", "raw_trace", "prompt_text", "tool_argument_value", "endpoint_value", "api_key_value", "full_url"):
        mutated = copy.deepcopy(data)
        mutated["records"][0][key] = "redacted"
        assert any("forbidden_key" in blocker or "extra_fields" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["note"] = "https://provider.example/raw request body"
    assert any("forbidden_value" in blocker or "extra_fields" in blocker for blocker in validate_artifact(mutated))


def test_runner_source_does_not_source_profile_or_import_network_client() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "/cephfs/qiuyn/.profile" not in source
    assert "source /cephfs/qiuyn/.profile" not in source
    assert "source(" not in source
    assert "requests." not in source
    assert "subprocess" not in source
