from scripts.abhe_v0_runtime_slot_controller import (
    prerequisite_lookup_planner_v0,
    prior_tool_observation_slot_binder_v0,
    required_arg_schema_reader_v0,
    runtime_slot_controller_v2,
    valid_tool_call_guard_v0,
)
from scripts.run_abhe_v0_runtime_slot_micro_harness import build as build_micro
from scripts.build_abhe_v0_runtime_slot_controller_diagnostic import build as build_diagnostic


def _tool(name="book", required=None, types=None):
    required = required or ["city", "date", "party_size"]
    types = types or {"city": "string", "date": "string", "party_size": "integer"}
    return {
        "type": "function",
        "function": {
            "name": name,
            "parameters": {
                "type": "object",
                "properties": {slot: {"type": types.get(slot, "string")} for slot in required},
                "required": required,
            },
        },
    }


def test_required_arg_schema_reader_reads_wrapper_schema():
    read = required_arg_schema_reader_v0(_tool())
    assert read["required_arg_count"] == 3
    assert read["required_args"] == ["city", "date", "party_size"]
    assert read["property_type_by_arg"]["party_size"] == "integer"


def test_valid_tool_call_guard_allows_complete_call_without_blocking():
    read = required_arg_schema_reader_v0(_tool())
    guard = valid_tool_call_guard_v0({"arguments": {"city": "x", "date": "y", "party_size": 2}}, read)
    assert guard["tool_call_valid"] is True
    assert guard["allow_without_rewrite"] is True
    assert guard["would_block_valid_tool_call"] is False


def test_valid_tool_call_guard_detects_missing_and_incompatible_args():
    read = required_arg_schema_reader_v0(_tool())
    guard = valid_tool_call_guard_v0({"arguments": {"city": "x", "party_size": "two"}}, read)
    assert guard["tool_call_valid"] is False
    assert guard["missing_required_args"] == ["date"]
    assert guard["incompatible_required_args"] == ["party_size"]


def test_prior_tool_observation_slot_binder_binds_only_unambiguous_compatible_source():
    read = required_arg_schema_reader_v0(_tool())
    bind = prior_tool_observation_slot_binder_v0(
        read,
        {"arguments": {"city": "x", "date": "y"}},
        [{"source_type": "prior_tool_observation", "values": {"party_size": 2}}],
    )
    assert bind["bound_slot_sources"] == {"party_size": "prior_tool_observation"}
    assert bind["ambiguous_slots"] == []


def test_prior_tool_observation_slot_binder_refuses_ambiguous_source():
    read = required_arg_schema_reader_v0(_tool(required=["city"]))
    bind = prior_tool_observation_slot_binder_v0(
        read,
        {"arguments": {}},
        [
            {"source_type": "prior_confirmed_selection", "values": {"city": "a"}},
            {"source_type": "prior_tool_observation", "values": {"city": "b"}},
        ],
    )
    assert bind["bound_slot_sources"] == {}
    assert bind["ambiguous_slots"] == ["city"]


def test_prerequisite_lookup_planner_plans_only_available_lookup():
    plan = prerequisite_lookup_planner_v0(
        ["city", "date"],
        [_tool(name="lookup_city", required=["landmark"])],
        {"city": "lookup_city", "date": "lookup_date"},
    )
    assert plan["planned_lookup_by_slot"] == {"city": "lookup_city"}
    assert plan["unrecoverable_slots"] == ["date"]
    assert plan["ask_or_insufficient_required"] is True


def test_runtime_slot_controller_v2_decisions():
    tool = _tool()
    assert runtime_slot_controller_v2(tool, {"arguments": {"city": "x", "date": "y", "party_size": 2}}, [], [], {})["decision"] == "allow_valid_tool_call"
    assert runtime_slot_controller_v2(tool, {"arguments": {"city": "x", "date": "y"}}, [{"source_type": "prior_tool_observation", "values": {"party_size": 2}}], [], {})["decision"] == "bind_recovered_slots_then_call"
    assert runtime_slot_controller_v2(tool, {"arguments": {"date": "y", "party_size": 2}}, [], [_tool(name="lookup_city", required=["landmark"])], {"city": "lookup_city"})["decision"] == "call_prerequisite_lookup"


def test_runtime_slot_micro_harness_passes_and_stays_non_executing():
    report = build_micro()
    assert report["micro_harness_passed"] is True
    assert report["fixture_count"] == 50
    assert report["provider_calls_made"] is False
    assert report["scorer_called"] is False
    assert report["performance_evidence"] is False


def test_runtime_slot_controller_diagnostic_reports_phase_c_boundary():
    report = build_diagnostic()
    assert report["phase_b_micro_harness_ready"] is True
    assert report["performance_evidence"] is False
    if report.get("phase_c_bfcl_rerun_completed"):
        assert report["phase_c_bfcl_rerun_ready"] is True
        assert report["next_required_action"] in {"confirm_mechanism_with_actual_bind_repairs_before_promotion", "review_runtime_slot_controller_v2_for_promotion"}
    else:
        assert report["phase_c_bfcl_rerun_ready"] is False
        assert "runtime_slot_controller_v2_not_integrated_into_proxy_request_response_path" in report["phase_c_blockers"]



def _chat_tool(required=None, types=None):
    return _tool(name="book_table", required=required, types=types)


def _tool_call(args):
    import json
    return {
        "id": "call_1",
        "type": "function",
        "function": {"name": "book_table", "arguments": json.dumps(args, ensure_ascii=False)},
    }


def _engine(tmp_path):
    from grc.runtime.engine import RuleEngine
    return RuleEngine(str(tmp_path), runtime_policy={})


def test_engine_runtime_slot_controller_binds_missing_arg_from_structured_tool_observation(tmp_path):
    import json
    from grc.runtime.slot_controller import ABHE_RUNTIME_SLOT_CONTROLLER_PATCH

    request = {
        "messages": [{"role": "tool", "tool_call_id": "prior", "content": json.dumps({"party_size": 2})}],
        "tools": [_chat_tool()],
    }
    response = {"choices": [{"message": {"tool_calls": [_tool_call({"city": "c", "date": "d"})]}}]}
    final, repairs, validation = _engine(tmp_path).apply_response(request, response, request_patches=[ABHE_RUNTIME_SLOT_CONTROLLER_PATCH])
    final_args = json.loads(final["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
    assert final_args["party_size"] == 2
    assert not validation.issues
    assert any(repair.get("kind") == "abhe_runtime_slot_controller_v2_bind_required_slot" for repair in repairs)
    assert all("value" not in repair for repair in repairs if repair.get("kind") == "abhe_runtime_slot_controller_v2_bind_required_slot")
    assert "abhe_runtime_slot_controller_v2" in validation.policy_hits


def test_engine_runtime_slot_controller_does_not_rewrite_valid_tool_call(tmp_path):
    import json
    from grc.runtime.slot_controller import ABHE_RUNTIME_SLOT_CONTROLLER_PATCH

    request = {"messages": [], "tools": [_chat_tool()]}
    response = {"choices": [{"message": {"tool_calls": [_tool_call({"city": "c", "date": "d", "party_size": 2})]}}]}
    final, repairs, validation = _engine(tmp_path).apply_response(request, response, request_patches=[ABHE_RUNTIME_SLOT_CONTROLLER_PATCH])
    final_args = json.loads(final["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
    assert final_args == {"city": "c", "date": "d", "party_size": 2}
    assert not repairs
    assert not validation.issues


def test_engine_runtime_slot_controller_refuses_ambiguous_binding(tmp_path):
    import json
    from grc.runtime.slot_controller import ABHE_RUNTIME_SLOT_CONTROLLER_PATCH

    request = {
        "messages": [
            {"role": "tool", "tool_call_id": "one", "content": json.dumps({"party_size": 2})},
            {"role": "tool", "tool_call_id": "two", "content": json.dumps({"party_size": 3})},
        ],
        "tools": [_chat_tool()],
    }
    response = {"choices": [{"message": {"tool_calls": [_tool_call({"city": "c", "date": "d"})]}}]}
    final, repairs, validation = _engine(tmp_path).apply_response(request, response, request_patches=[ABHE_RUNTIME_SLOT_CONTROLLER_PATCH])
    final_args = json.loads(final["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
    assert "party_size" not in final_args
    assert not any(repair.get("kind") == "abhe_runtime_slot_controller_v2_bind_required_slot" for repair in repairs)
    assert validation.issues


def test_runtime_slot_controller_path_replay_artifact_passes():
    from scripts.check_abhe_v0_runtime_slot_controller_path_replay import check

    report = check()
    assert report["path_replay_check_passed"] is True
    assert report["proxy_fixture_runtime_path_confirmed"] is True
    assert report["same_request_noop_replay_confirmed"] is True
    assert report["performance_evidence"] is False


def test_runtime_slot_controller_bindability_audit_artifact_passes():
    from scripts.check_abhe_v0_runtime_slot_controller_bindability import check

    report = check()
    assert report["bindability_audit_check_passed"] is True
    assert report["target_trace_row_count"] >= 1
    assert report["slot_bind_repair_count"] == 0
    assert report["bindable_missing_required_arg_row_count"] == 0
    assert report["mechanism_promotion_allowed"] is False
    assert report["performance_evidence"] is False


def test_runtime_slot_observability_plan_artifact_passes():
    from scripts.check_abhe_v0_runtime_slot_observability_plan import check

    report = check()
    assert report["observability_plan_check_passed"] is True
    assert report["observability_plan_ready"] is True
    assert report["bfcl_rerun_authorized_by_this_plan"] is False
    assert report["performance_evidence"] is False
    assert report["next_required_action"] == "implement_pre_generation_post_decode_observability_no_provider_fixture_before_bfcl_rerun"


def test_runtime_slot_observability_fixture_artifact_passes():
    from scripts.check_abhe_v0_runtime_slot_observability_fixture import check

    report = check()
    assert report["observability_fixture_check_passed"] is True
    assert report["fixture_count"] == 4
    assert report["bind_repair_rows"] == 1
    assert report["provider_generated_valid_call_proxy_rows"] == 1
    assert report["no_tool_final_response_rows"] == 1
    assert report["performance_evidence"] is False


def test_runtime_slot_observability_review_artifact_passes():
    from scripts.check_abhe_v0_runtime_slot_observability_review import check

    report = check()
    assert report["observability_review_check_passed"] is True
    assert report["observability_review_passed"] is True
    assert report["bfcl_rerun_authorized"] is False
    assert report["performance_evidence"] is False
    assert report["next_required_action"] == "request_bounded_bfcl_rerun_approval_with_observability_enabled"


def test_runtime_slot_scorer_unit_diagnostic_artifact_passes():
    from scripts.build_abhe_v0_runtime_slot_scorer_unit_diagnostic import build
    from scripts.check_abhe_v0_runtime_slot_scorer_unit_diagnostic import check

    artifact = build()
    assert artifact["performance_evidence"] is False
    assert artifact["summary"]["more_bfcl_before_alignment_recommended"] is False
    assert artifact["summary"]["target_compact_to_scorer_unit_collapse_factor"] > 1
    report = check()
    assert report["scorer_unit_diagnostic_check_passed"] is True
    assert report["target_strict_per_compact_case_pairing_available"] is False
    assert report["performance_evidence"] is False


def test_runtime_slot_scorer_unit_matrix_artifact_passes():
    from scripts.build_abhe_v0_runtime_slot_scorer_unit_matrix import build
    from scripts.check_abhe_v0_runtime_slot_scorer_unit_matrix import check

    artifact = build()
    assert artifact["performance_evidence"] is False
    assert artifact["summary"]["target_score_record_count"] == 1
    assert artifact["summary"]["target_compact_to_score_record_factor"] > 1
    report = check()
    assert report["scorer_unit_matrix_check_passed"] is True
    assert report["target_strict_per_compact_case_pairing_available"] is False
    assert report["performance_evidence"] is False


def test_runtime_slot_per_selected_id_matrix_artifact_passes():
    from scripts.build_abhe_v0_runtime_slot_per_selected_id_matrix import build
    from scripts.check_abhe_v0_runtime_slot_per_selected_id_matrix import check

    artifact = build()
    assert artifact["performance_evidence"] is False
    assert artifact["summary"]["selected_row_count"] == 48
    assert artifact["summary"]["target_selected_compact_case_count"] == 24
    assert artifact["summary"]["target_unique_scorer_unit_count"] == 1
    assert artifact["summary"]["target_per_selected_id_pass_available"] is False
    assert artifact["summary"]["target_pass_is_scorer_unit_inherited"] is True
    report = check()
    assert report["per_selected_id_matrix_check_passed"] is True
    assert report["target_per_selected_id_pass_available"] is False
    assert report["target_pass_is_scorer_unit_inherited"] is True
    assert report["performance_evidence"] is False


def test_runtime_slot_scorer_unit_distinct_slice_artifact_passes():
    from scripts.build_abhe_v0_runtime_slot_scorer_unit_distinct_slice import build
    from scripts.check_abhe_v0_runtime_slot_scorer_unit_distinct_slice import check

    artifact = build()
    assert artifact["performance_evidence"] is False
    assert artifact["scorer_unit_distinct_slice_ready"] is True
    assert artifact["selected_case_count"] == 48
    assert artifact["target_selected_compact_case_count"] == 24
    assert artifact["target_unique_scorer_unit_count"] == 24
    assert artifact["target_compact_to_scorer_unit_factor"] == 1.0
    assert artifact["archive_source_overlap_count"] == 0
    assert artifact["prior_slice_overlap_count"] == 0
    report = check()
    assert report["scorer_unit_distinct_slice_check_passed"] is True
    assert report["target_compact_to_scorer_unit_factor"] == 1.0
    assert report["performance_evidence"] is False


def test_runtime_slot_distinct_rerun_request_artifact_passes():
    from scripts.check_abhe_v0_runtime_slot_distinct_rerun_request import check

    report = check()
    assert report["distinct_rerun_request_passed"] is True
    assert report["authorized"] is False
    assert report["runner_manifest_compatible"] is True
    assert report["target_compact_to_scorer_unit_factor"] == 1.0
    assert report["performance_evidence"] is False


def test_runtime_slot_distinct_runner_dry_run_stays_non_executing():
    from pathlib import Path
    from scripts.run_abhe_v0_runtime_slot_controller_residual_dev_smoke import dry_run_arm

    report = dry_run_arm("baseline", Path("outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_scorer_unit_distinct_slice_plan.json"))
    assert report["runner_manifest_compatible"] is True
    assert report["selected_case_count"] == 48
    assert report["provider_calls_made"] is False
    assert report["bfcl_generate_called"] is False
    assert report["bfcl_evaluate_called"] is False
    assert report["scorer_called"] is False
    assert report["performance_evidence"] is False


def test_runtime_slot_score_output_contract_gap_audit_artifact_passes():
    from pathlib import Path
    from scripts.build_abhe_v0_runtime_slot_score_output_contract_gap_audit import OUTPUT, build
    from scripts.check_abhe_v0_runtime_slot_score_output_contract_gap_audit import check

    before = Path(OUTPUT).read_text(encoding="utf-8")
    artifact = build(write=False)
    assert Path(OUTPUT).read_text(encoding="utf-8") == before
    assert artifact["performance_evidence"] is False
    assert artifact["summary"]["contract_gap_confirmed"] is True
    assert artifact["summary"]["per_selected_labels_recoverable"] is False
    assert artifact["summary"]["per_turn_labels_recoverable"] is False
    assert artifact["summary"]["target_selected_to_score_total_factor"] > 1
    report = check()
    assert report["score_output_contract_gap_audit_passed"] is True
    assert report["contract_gap_confirmed"] is True
    assert report["per_selected_labels_recoverable"] is False
    assert report["per_turn_labels_recoverable"] is False
    assert report["performance_evidence"] is False


def test_runtime_slot_alignment_sidecar_artifact_passes():
    from pathlib import Path
    from scripts.build_abhe_v0_runtime_slot_alignment_sidecar import DEFAULT_OUTPUT, build
    from scripts.check_abhe_v0_runtime_slot_alignment_sidecar import check

    before = Path(DEFAULT_OUTPUT).read_text(encoding="utf-8")
    artifact = build(write=False)
    assert Path(DEFAULT_OUTPUT).read_text(encoding="utf-8") == before
    assert artifact["performance_evidence"] is False
    assert artifact["selected_case_ids_hash"] == artifact["summary"]["selected_case_ids_hash"]
    assert artifact["summary"]["alignment_sidecar_ready"] is True
    assert artifact["summary"]["selected_count"] == 48
    assert artifact["summary"]["row_count"] == 144
    assert artifact["summary"]["per_selected_valid_labels_available"] is False
    assert artifact["summary"]["per_turn_valid_labels_available"] is False
    report = check()
    assert report["alignment_sidecar_check_passed"] is True
    assert report["alignment_sidecar_ready"] is True
    assert report["selected_case_ids_hash"] == artifact["selected_case_ids_hash"]
    assert report["performance_evidence"] is False
