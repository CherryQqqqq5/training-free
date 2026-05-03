from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.check_bfcl_generate_failure_telemetry_artifact import (
    DEFAULT_ARTIFACT as DEFAULT_TELEMETRY_ARTIFACT,
    OPTIONAL_PREGENERATE_SUBSTAGE_FIELDS,
    check as check_artifact,
    validate as validate_artifact,
)
from scripts.check_bfcl_generate_failure_telemetry_gate import (
    DEFAULT_PACKET,
    REQUIRED_COMPACT_FIELDS,
    check,
    validate_packet,
)
import scripts.run_bfcl_generate_failure_telemetry as runner

build_plan = runner.build_plan
classify_bfcl_cli_failure = runner.classify_bfcl_cli_failure
classify_category_arg_shape = runner.classify_category_arg_shape
classify_category_arg_validation = runner.classify_category_arg_validation
classify_pregenerate_substage_labels = runner.classify_pregenerate_substage_labels
classify_provider_proxy_status = runner.classify_provider_proxy_status
execute_generate_failure_telemetry = runner.execute_generate_failure_telemetry


def _packet() -> dict:
    return json.loads(DEFAULT_PACKET.read_text(encoding="utf-8"))


def _pending_packet(tmp_path: Path) -> Path:
    data = _packet()
    data["approval_status"] = "pending"
    for key in (
        "authorized",
        "provider_request_authorized",
        "bfcl_generate_authorized",
        "bfcl_smoke_authorized",
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
    path = tmp_path / "pending_generate_failure_telemetry_packet.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _approved_packet(tmp_path: Path) -> Path:
    data = _packet()
    data["approval_status"] = "approved"
    data["authorized"] = True
    data["provider_request_authorized"] = True
    data["bfcl_generate_authorized"] = True
    for key in (
        "bfcl_smoke_authorized",
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
    path = tmp_path / "approved_generate_failure_telemetry_packet.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def test_committed_packet_matches_post_execution_lifecycle() -> None:
    summary = check(DEFAULT_PACKET)
    assert summary["bfcl_generate_failure_telemetry_gate_passed"] is True
    assert summary["approval_status"] == "approved"
    assert summary["authorized"] is True
    assert summary["provider_request_authorized"] is True
    assert summary["bfcl_generate_authorized"] is True
    assert summary["route_profile"] == "novacode"
    assert summary["route_model"] == "gpt-4.1"
    assert summary["compact_field_count"] == len(REQUIRED_COMPACT_FIELDS)
    assert summary["performance_evidence"] is False


def test_pending_fixture_rejects_authorized_true(tmp_path: Path) -> None:
    base = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    data = copy.deepcopy(base)
    data["authorized"] = True
    blockers = validate_packet(data)
    assert any("authorized_not_false" in blocker for blocker in blockers)


def test_rejects_provider_generate_evaluate_scorer_full_baseline_flags(tmp_path: Path) -> None:
    base = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    for key in (
        "provider_request_authorized",
        "bfcl_generate_authorized",
        "bfcl_smoke_authorized",
        "bfcl_evaluate_authorized",
        "scorer_authorized",
        "full_baseline_authorized",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        blockers = validate_packet(data)
        assert any(key in blocker for blocker in blockers)


def test_rejects_candidate_and_performance_claim_flags(tmp_path: Path) -> None:
    base = json.loads(_pending_packet(tmp_path).read_text(encoding="utf-8"))
    for key in (
        "candidate_runtime_activation_authorized",
        "candidate_jsonl_authorized",
        "candidate_pool_ready",
        "performance_evidence",
        "sota_3pp_claim_ready",
        "huawei_acceptance_ready",
        "scorer_feedback_used",
    ):
        data = copy.deepcopy(base)
        data[key] = True
        blockers = validate_packet(data)
        assert any(key in blocker for blocker in blockers)


def test_rejects_route_fallback_openrouter_and_active_gpt52() -> None:
    for key, value in (
        ("route_profile", "other"),
        ("route_model", "gpt-5.2"),
        ("fallback_allowed", True),
        ("gpt_4o_fallback_allowed", True),
        ("openrouter_allowed", True),
        ("gpt_5_2_active", True),
    ):
        data = _packet()
        data[key] = value
        assert validate_packet(data)


def test_rejects_raw_field_names_and_endpoint_key_literal() -> None:
    data = _packet()
    data["allowed_compact_fields"] = list(REQUIRED_COMPACT_FIELDS) + ["raw_prompt"]
    assert any("extra_compact_fields" in blocker or "forbidden_compact_field" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["endpoint_value"] = "shape_only"
    assert any("forbidden_key" in blocker for blocker in validate_packet(data))
    data = _packet()
    data["note"] = "sk-" + "A" * 32
    assert any("forbidden_value" in blocker for blocker in validate_packet(data))


def test_rejects_missing_required_compact_fields() -> None:
    data = _packet()
    data["allowed_compact_fields"] = [field for field in REQUIRED_COMPACT_FIELDS if field != "suspected_generate_failure_stage"]
    blockers = validate_packet(data)
    assert any("missing_required_compact_fields" in blocker for blocker in blockers)
    assert any("required_generate_stage_field_missing" in blocker for blocker in blockers)


def test_dry_run_does_not_source_env_read_secrets_or_execute_paths() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["blockers"] == []
    assert plan["env_profile_sourced"] is False
    assert plan["endpoint_value_read"] is False
    assert plan["api_key_value_read"] is False
    assert plan["baseline_command_executed"] is False
    assert plan["generate_stage_entered"] is False
    assert plan["provider_call_started"] is False
    assert plan["bfcl_generate_executed"] is False
    assert plan["bfcl_smoke_executed"] is False
    assert plan["bfcl_evaluate_executed"] is False
    assert plan["scorer_executed"] is False
    assert plan["full_baseline_executed"] is False
    assert plan["performance_evidence"] is False


def test_dry_run_includes_required_compact_field_schema() -> None:
    plan = build_plan(DEFAULT_PACKET)
    assert plan["compact_fields"] == REQUIRED_COMPACT_FIELDS
    assert "generate_exact_exit_code" in plan["compact_fields"]
    assert "bfcl_cli_exception_class" in plan["compact_fields"]
    assert "suspected_generate_failure_stage" in plan["compact_fields"]


def test_provider_proxy_status_classifier_labels() -> None:
    assert classify_provider_proxy_status("HTTP status 200", generate_entered=True) == ("2xx", "completed_2xx")
    assert classify_provider_proxy_status("HTTP status 404", generate_entered=True) == ("4xx", "completed_non2xx")
    assert classify_provider_proxy_status("HTTP status 503", generate_entered=True) == ("5xx", "completed_non2xx")
    assert classify_provider_proxy_status("request timed out", generate_entered=True) == ("timeout", "timeout")
    assert classify_provider_proxy_status("failed to connect to 127.0.0.1 connection refused", generate_entered=True) == ("proxy_unreachable", "connection_error")
    assert classify_provider_proxy_status("ConnectionError max retries exceeded", generate_entered=True) == ("connection_error", "connection_error")
    assert classify_provider_proxy_status("local endpoint 127.0.0.1 without provider call", generate_entered=False) == ("not_observed", "not_observed")
    assert classify_provider_proxy_status("local endpoint 127.0.0.1", generate_entered=True) == ("unknown_compact", "unknown_compact")
    assert classify_provider_proxy_status("", generate_entered=False) == ("not_observed", "not_observed")


def test_bfcl_cli_failure_classifier_labels() -> None:
    assert classify_bfcl_cli_failure(0, "", provider_status_class="not_observed", generate_entered=True, result_file_count=1) == ("none_observed", "none_observed")
    assert classify_bfcl_cli_failure(1, "ModuleNotFoundError: no module named shape", provider_status_class="not_observed", generate_entered=False, result_file_count=0) == ("import_error", "generate_command_setup")
    assert classify_bfcl_cli_failure(1, "usage: generate error: unrecognized arguments", provider_status_class="not_observed", generate_entered=False, result_file_count=0) == ("command_config_error", "generate_command_setup")
    assert classify_bfcl_cli_failure(1, "result path no such file or directory", provider_status_class="not_observed", generate_entered=True, result_file_count=0) == ("result_path_error", "result_materialization")
    assert classify_bfcl_cli_failure(1, "provider returned HTTP status 500", provider_status_class="5xx", generate_entered=True, result_file_count=0) == ("proxy_or_provider_error", "proxy_request")
    assert classify_bfcl_cli_failure(1, "Traceback runtime exception", provider_status_class="not_observed", generate_entered=True, result_file_count=0) == ("runtime_exception", "unknown_generate")
    assert classify_bfcl_cli_failure(2, "opaque failure", provider_status_class="not_observed", generate_entered=True, result_file_count=1) == ("unknown_nonzero", "unknown_generate")


def test_execute_with_pending_packet_fails_closed_before_env_provider_or_bfcl(tmp_path: Path) -> None:
    pending = _pending_packet(tmp_path)
    summary = execute_generate_failure_telemetry(pending, tmp_path / "telemetry.json")
    assert "generate_failure_telemetry_packet_not_approved" in summary["blockers"]
    assert summary["env_profile_sourced"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False
    assert summary["baseline_command_executed"] is False
    assert summary["generate_stage_entered"] is False
    assert summary["provider_call_started"] is False
    assert summary["bfcl_generate_executed"] is False
    assert summary["bfcl_evaluate_executed"] is False
    assert summary["scorer_executed"] is False


def test_execute_with_pending_packet_rejects_preexisting_output_before_any_execution(tmp_path: Path) -> None:
    pending = _pending_packet(tmp_path)
    output = tmp_path / "telemetry.json"
    output.write_text("{}", encoding="utf-8")
    summary = execute_generate_failure_telemetry(pending, output)
    assert "output_artifact_exists" in summary["blockers"]
    assert summary["baseline_command_executed"] is False
    assert summary["endpoint_value_read"] is False
    assert summary["api_key_value_read"] is False


def test_approved_execute_path_uses_mocked_command_stops_before_evaluate_and_writes_compact_artifact(tmp_path: Path) -> None:
    packet = _approved_packet(tmp_path)
    output = tmp_path / "telemetry.json"

    def fake_run(command, cwd, env, stdout, stderr, check):
        assert command[:3] == ["bash", "-lc", "set +x; set -a; source /cephfs/qiuyn/.profile >/dev/null 2>&1; set +a; exec \"$@\""]
        assert "scripts/run_bfcl_v4_baseline.sh" in command
        assert env["GRC_UPSTREAM_PROFILE"] == "novacode"
        assert env["GRC_UPSTREAM_MODEL"] == "gpt-4.1"
        assert env["GRC_BFCL_STOP_AFTER_GENERATE"] == "1"
        stage_path = Path(env["GRC_BASELINE_STAGE_TELEMETRY_PATH"])
        run_root = Path(command[6])
        result_file = run_root / "bfcl" / "result" / "shape.json"
        result_file.parent.mkdir(parents=True, exist_ok=True)
        result_file.write_text("{}", encoding="utf-8")
        stdout.write(b"HTTP status 200\n")
        stage_path.write_text(
            "\n".join(
                [
                    json.dumps({"stage": "validate_model_split", "event": "started"}),
                    json.dumps({"stage": "validate_model_split", "event": "completed"}),
                    json.dumps({"stage": "ensure_upstream_auth", "event": "started"}),
                    json.dumps({"stage": "ensure_upstream_auth", "event": "completed"}),
                    json.dumps({"stage": "start_proxy", "event": "started"}),
                    json.dumps({"stage": "start_proxy", "event": "completed"}),
                    json.dumps({"stage": "preflight", "event": "started"}),
                    json.dumps({"stage": "preflight", "event": "completed"}),
                    json.dumps({"stage": "pregenerate_config_source", "event": "started"}),
                    json.dumps({"stage": "pregenerate_config_source", "event": "completed", "config_source_exit_class": "ok"}),
                    json.dumps({"stage": "pregenerate_env_default_expansion", "event": "started"}),
                    json.dumps({"stage": "pregenerate_env_default_expansion", "event": "completed", "env_default_expansion_class": "ok"}),
                    json.dumps({"stage": "pregenerate_category_arg_assembly", "event": "started"}),
                    json.dumps({"stage": "pregenerate_category_arg_assembly", "event": "completed", "category_arg_assembly_shape": "single_comma_joined_test_category_argument"}),
                    json.dumps({"stage": "pregenerate_category_arg_validation", "event": "started"}),
                    json.dumps({"stage": "pregenerate_category_arg_validation", "event": "completed", "category_arg_validation_result": "accepted_by_static_shape"}),
                    json.dumps({"stage": "pregenerate_bfcl_cli_import_probe", "event": "started"}),
                    json.dumps({"stage": "pregenerate_bfcl_cli_import_probe", "event": "completed", "bfcl_cli_import_probe_class_without_generate": "not_run_by_design"}),
                    json.dumps({"stage": "pregenerate_bfcl_cli_argument_probe", "event": "started"}),
                    json.dumps({"stage": "pregenerate_bfcl_cli_argument_probe", "event": "completed", "bfcl_cli_argument_probe_class_without_generate": "not_run_by_design"}),
                    json.dumps({"stage": "pregenerate_marker_boundary", "event": "started"}),
                    json.dumps({"stage": "pregenerate_marker_boundary", "event": "completed", "pre_generate_marker_boundary_class": "after_preflight_before_bfcl_generate"}),
                    json.dumps({"stage": "bfcl_generate", "event": "started"}),
                    json.dumps({"stage": "bfcl_generate", "event": "completed"}),
                    json.dumps({"stage": "stop_after_generate", "event": "started"}),
                    json.dumps({"stage": "stop_after_generate", "event": "completed"}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return runner.subprocess.CompletedProcess(command, 0)

    summary = execute_generate_failure_telemetry(packet, output, run_command=fake_run)
    assert summary["blockers"] == []
    assert summary["baseline_command_executed"] is True
    assert summary["generate_stage_entered"] is True
    assert summary["bfcl_generate_executed"] is True
    assert summary["generate_exact_exit_code"] == 0
    assert summary["generate_exit_code_class"] == "zero"
    assert summary["result_file_count_after_generate"] == 1
    assert summary["bfcl_evaluate_started"] is False
    assert summary["scorer_started"] is False
    assert summary["raw_outputs_removed"] is True
    assert summary["env_profile_sourced"] is True
    assert summary["endpoint_value_read"] is True
    assert summary["api_key_value_read"] is True
    assert summary["provider_status_class_during_generate"] == "2xx"
    assert summary["provider_call_completed_class"] == "completed_2xx"
    assert summary["bfcl_cli_exception_class"] == "none_observed"
    assert summary["bfcl_cli_exception_stage_label"] == "none_observed"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["artifact_kind"] == "bfcl_generate_failure_telemetry_compact"
    record = payload["records"][0]
    assert set(REQUIRED_COMPACT_FIELDS).issubset(record)
    assert set(OPTIONAL_PREGENERATE_SUBSTAGE_FIELDS).issubset(record)
    assert record["bfcl_evaluate_started"] is False
    assert record["scorer_started"] is False
    assert record["performance_evidence"] is False
    assert record["config_source_exit_class"] == "ok"
    assert record["env_default_expansion_class"] == "ok"
    assert record["category_arg_assembly_shape"] == "single_comma_joined_test_category_argument"
    assert record["category_arg_validation_result"] == "accepted_by_static_shape"
    assert record["bfcl_cli_import_probe_class_without_generate"] == "not_run_by_design"
    assert record["bfcl_cli_argument_probe_class_without_generate"] == "not_run_by_design"
    assert record["pre_generate_marker_boundary_class"] == "after_preflight_before_bfcl_generate"
    assert record["suspected_pregenerate_failure_substage"] == "none_generate_stage_entered"
    artifact_summary = check_artifact(output)
    assert artifact_summary["bfcl_generate_failure_telemetry_artifact_passed"] is True
    assert artifact_summary["suspected_generate_failure_stage"] == "generate_stage_completed_before_evaluate"


def test_approved_execute_path_records_generate_nonzero_without_raw_output(tmp_path: Path) -> None:
    packet = _approved_packet(tmp_path)
    output = tmp_path / "telemetry.json"

    def fake_run(command, cwd, env, stdout, stderr, check):
        stage_path = Path(env["GRC_BASELINE_STAGE_TELEMETRY_PATH"])
        stdout.write(b"provider returned HTTP status 500\n")
        stage_path.write_text(
            json.dumps({"stage": "bfcl_generate", "event": "started"}) + "\n",
            encoding="utf-8",
        )
        return runner.subprocess.CompletedProcess(command, 1)

    summary = execute_generate_failure_telemetry(packet, output, run_command=fake_run)
    assert summary["blockers"] == []
    assert summary["generate_exit_code_class"] == "nonzero_1"
    assert summary["provider_status_class_during_generate"] == "5xx"
    assert summary["provider_call_completed_class"] == "completed_non2xx"
    assert summary["bfcl_cli_exception_class"] == "proxy_or_provider_error"
    assert summary["bfcl_cli_exception_stage_label"] == "proxy_request"
    assert summary["stop_gate_triggered"] == "bfcl_generate_exit_nonzero"
    assert summary["suspected_generate_failure_stage"] == "bfcl_generate_nonzero_exit"
    assert summary["raw_outputs_removed"] is True



def test_generate_failure_artifact_checker_accepts_optional_pregenerate_substage_labels() -> None:
    data = json.loads(DEFAULT_TELEMETRY_ARTIFACT.read_text(encoding="utf-8"))
    record = data["records"][0]
    record.update(
        {
            "config_source_exit_class": "ok",
            "env_default_expansion_class": "ok",
            "category_arg_assembly_shape": "single_comma_joined_test_category_argument",
            "category_arg_validation_result": "accepted_by_static_shape",
            "bfcl_cli_import_probe_class_without_generate": "not_run_by_design",
            "bfcl_cli_argument_probe_class_without_generate": "not_run_by_design",
            "pre_generate_marker_boundary_class": "after_preflight_before_bfcl_generate",
            "last_started_stage": "preflight",
            "last_completed_stage": "preflight",
            "suspected_pregenerate_failure_substage": "category_arg_validation_or_command_setup",
        }
    )
    assert set(OPTIONAL_PREGENERATE_SUBSTAGE_FIELDS).issubset(record)
    assert validate_artifact(data) == []


def test_generate_failure_artifact_checker_rejects_invalid_optional_pregenerate_label() -> None:
    data = json.loads(DEFAULT_TELEMETRY_ARTIFACT.read_text(encoding="utf-8"))
    data["records"][0]["category_arg_validation_result"] = "raw_prompt"
    blockers = validate_artifact(data)
    assert any("category_arg_validation_result_invalid" in blocker for blocker in blockers)



def test_pregenerate_category_arg_shape_and_validation_classifiers() -> None:
    assert classify_category_arg_shape("") == "empty_test_category_argument"
    assert classify_category_arg_shape("simple") == "single_category_argument"
    assert classify_category_arg_shape("simple,multiple") == "single_comma_joined_test_category_argument"
    assert classify_category_arg_validation("") == "not_validated_without_execution"
    assert classify_category_arg_validation("simple,multi_turn_base") == "accepted_by_static_shape"
    assert classify_category_arg_validation("simple, multi_turn_base") == "rejected_by_static_shape"
    assert classify_category_arg_validation("simple,,multiple") == "rejected_by_static_shape"


def test_pregenerate_substage_labels_from_synthetic_stage_events() -> None:
    events = [
        {"stage": "preflight", "event": "started"},
        {"stage": "preflight", "event": "completed"},
        {"stage": "pregenerate_config_source", "event": "started"},
        {"stage": "pregenerate_config_source", "event": "completed", "config_source_exit_class": "ok"},
        {"stage": "pregenerate_env_default_expansion", "event": "started"},
        {"stage": "pregenerate_env_default_expansion", "event": "completed", "env_default_expansion_class": "ok"},
        {"stage": "pregenerate_category_arg_assembly", "event": "started"},
        {"stage": "pregenerate_category_arg_assembly", "event": "completed", "category_arg_assembly_shape": "single_comma_joined_test_category_argument"},
        {"stage": "pregenerate_category_arg_validation", "event": "started"},
        {"stage": "pregenerate_category_arg_validation", "event": "completed", "category_arg_validation_result": "accepted_by_static_shape"},
        {"stage": "pregenerate_bfcl_cli_import_probe", "event": "started"},
        {"stage": "pregenerate_bfcl_cli_import_probe", "event": "completed", "bfcl_cli_import_probe_class_without_generate": "not_run_by_design"},
        {"stage": "pregenerate_bfcl_cli_argument_probe", "event": "started"},
        {"stage": "pregenerate_bfcl_cli_argument_probe", "event": "completed", "bfcl_cli_argument_probe_class_without_generate": "not_run_by_design"},
        {"stage": "pregenerate_marker_boundary", "event": "started"},
        {"stage": "pregenerate_marker_boundary", "event": "completed", "pre_generate_marker_boundary_class": "after_preflight_before_bfcl_generate"},
    ]
    labels = classify_pregenerate_substage_labels(events, generate_entered=False)
    assert labels["config_source_exit_class"] == "ok"
    assert labels["env_default_expansion_class"] == "ok"
    assert labels["category_arg_validation_result"] == "accepted_by_static_shape"
    assert labels["bfcl_cli_import_probe_class_without_generate"] == "not_run_by_design"
    assert labels["bfcl_cli_argument_probe_class_without_generate"] == "not_run_by_design"
    assert labels["last_started_stage"] == "pregenerate_marker_boundary"
    assert labels["last_completed_stage"] == "pregenerate_marker_boundary"
    assert labels["suspected_pregenerate_failure_substage"] == "after_pregenerate_marker_boundary_before_bfcl_generate"


def test_pregenerate_substage_failure_label_precedence() -> None:
    labels = classify_pregenerate_substage_labels(
        [{"stage": "pregenerate_config_source", "event": "completed", "config_source_exit_class": "missing"}],
        generate_entered=False,
    )
    assert labels["suspected_pregenerate_failure_substage"] == "config_source"
    labels = classify_pregenerate_substage_labels(
        [{"stage": "pregenerate_category_arg_validation", "event": "completed", "category_arg_validation_result": "rejected_by_static_shape"}],
        generate_entered=False,
    )
    assert labels["suspected_pregenerate_failure_substage"] == "category_arg_validation"
    labels = classify_pregenerate_substage_labels(
        [{"stage": "pregenerate_category_arg_validation", "event": "started"}],
        generate_entered=False,
    )
    assert labels["suspected_pregenerate_failure_substage"] == "pregenerate_category_arg_validation_not_completed"
    labels = classify_pregenerate_substage_labels(
        [{"stage": "pregenerate_marker_boundary", "event": "completed"}],
        generate_entered=True,
    )
    assert labels["suspected_pregenerate_failure_substage"] == "none_generate_stage_entered"
