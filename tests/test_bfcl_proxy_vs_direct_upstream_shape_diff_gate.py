from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_proxy_vs_direct_upstream_shape_diff_artifact import check as check_artifact
from scripts.check_bfcl_proxy_vs_direct_upstream_shape_diff_artifact import validate as validate_artifact
from scripts.check_bfcl_proxy_vs_direct_upstream_shape_diff_gate import (
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check,
    validate_packet,
)
import scripts.run_bfcl_proxy_vs_direct_upstream_shape_diff as runner

build_plan = runner.build_plan
execute_shape_diff = runner.execute_shape_diff


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
    return _write_packet(tmp_path, data, "approved_proxy_vs_direct_shape_diff_packet.json")


def test_committed_packet_is_pending_and_fail_closed() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_proxy_vs_direct_upstream_shape_diff_gate_passed"] is True
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
    assert summary["bfcl_proxy_vs_direct_upstream_shape_diff_gate_passed"] is True
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
    assert plan["env_profile_sourced"] is False
    assert plan["preflight_command_executed"] is False
    assert plan["provider_call_started"] is False
    assert plan["proxy_live_request_started"] is False
    assert plan["profile_sourced"] is False
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS
    rendered = json.dumps(plan, sort_keys=True)
    assert "/cephfs/qiuyn/.profile" not in rendered
    assert "https://" not in rendered
    assert "sk-" not in rendered
    assert "Bearer" not in rendered


def test_pending_execute_fails_closed_before_artifact(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    summary = execute_shape_diff(DEFAULT_PACKET, output)
    assert "shape_diff_packet_not_approved" in summary["blockers"]
    assert summary["preflight_command_executed"] is False
    assert summary["provider_call_started"] is False
    assert summary["proxy_live_request_started"] is False
    assert summary["profile_sourced"] is False
    assert not output.exists()


def test_output_guard_blocks_before_artifact_rewrite(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    output.write_text("{}", encoding="utf-8")
    summary = execute_shape_diff(_approved_packet(tmp_path), output)
    assert "output_artifact_exists" in summary["blockers"]
    assert summary["preflight_command_executed"] is False
    assert output.read_text(encoding="utf-8") == "{}"


def test_execute_detects_current_key_env_mismatch_and_shape_drift(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    summary = execute_shape_diff(_approved_packet(tmp_path), output)
    assert summary["blockers"] == []
    assert summary["direct_selected_api_key_env_label"] == "CHUANGZHI_API_KEY"
    assert summary["proxy_selected_api_key_env_label"] == "NOVACODE_API_KEY"
    assert summary["api_key_env_match"] is False
    assert summary["direct_selected_base_url_env_label"] == "GRC_UPSTREAM_BASE_URL"
    assert summary["proxy_selected_base_url_env_label"] == "GRC_UPSTREAM_BASE_URL"
    assert summary["base_url_env_match"] is True
    assert summary["model_label_match"] is True
    assert summary["tool_choice_shape_label"] == "function_object_aligned"
    assert summary["tools_shape_label"] == "chat_function_tools_aligned"
    assert summary["messages_shape_label"] == "direct_user_only_proxy_system_developer_user"
    assert summary["token_field_shape_label"] == "max_tokens_aligned"
    assert summary["runtime_patch_label"] == "nonzero_runtime_request_patch"
    assert summary["suspected_mismatch_label"] == "api_key_env_mismatch"
    assert summary["provider_call_started"] is False
    assert summary["proxy_live_request_started"] is False
    assert summary["profile_sourced"] is False
    assert summary["bfcl_generate_started"] is False
    assert summary["bfcl_evaluate_started"] is False
    assert summary["scorer_started"] is False
    assert summary["full_baseline_executed"] is False
    assert summary["source_collection_executed"] is False
    assert summary["source_diagnostics_executed"] is False
    assert summary["performance_evidence"] is False
    artifact_summary = check_artifact(output)
    assert artifact_summary["bfcl_proxy_vs_direct_upstream_shape_diff_artifact_passed"] is True
    rendered = json.dumps(summary, sort_keys=True) + output.read_text(encoding="utf-8")
    assert "https://" not in rendered
    assert "sk-" not in rendered
    assert "Bearer" not in rendered
    assert "raw response" not in rendered.lower()


def test_artifact_checker_rejects_raw_leaks_and_downstream_flags(tmp_path: Path) -> None:
    output = tmp_path / "artifact.json"
    execute_shape_diff(_approved_packet(tmp_path), output)
    data = json.loads(output.read_text(encoding="utf-8"))
    for key in (
        "provider_call_started",
        "proxy_live_request_started",
        "profile_sourced",
        "bfcl_generate_started",
        "bfcl_evaluate_started",
        "scorer_started",
        "full_baseline_executed",
        "source_collection_executed",
        "performance_evidence",
        "raw_outputs_committed",
    ):
        mutated = copy.deepcopy(data)
        mutated["records"][0][key] = True
        assert any(key in blocker for blocker in validate_artifact(mutated))
    for key in ("raw_response_body", "raw_header", "raw_trace", "prompt_text", "tool_argument_value", "endpoint_value", "api_key_value"):
        mutated = copy.deepcopy(data)
        mutated["records"][0][key] = "redacted"
        assert any("forbidden_key" in blocker or "extra_fields" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["note"] = "https://provider.example/raw response body"
    assert any("forbidden_value" in blocker or "extra_fields" in blocker for blocker in validate_artifact(mutated))
    mutated = copy.deepcopy(data)
    mutated["records"][0]["direct_selected_api_key_env_label"] = "sk-" + "A" * 32
    assert any("direct_selected_api_key_env_label_invalid" in blocker or "forbidden_value" in blocker for blocker in validate_artifact(mutated))


def test_runner_source_does_not_source_profile_or_call_provider() -> None:
    source = Path(runner.__file__).read_text(encoding="utf-8")
    assert "/cephfs/qiuyn/.profile" not in source
    assert "source /cephfs/qiuyn/.profile" not in source
    assert "source(" not in source
    assert "urlopen" not in source
    assert "httpx" not in source
    assert "requests." not in source
