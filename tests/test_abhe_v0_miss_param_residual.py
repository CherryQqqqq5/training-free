from scripts.build_abhe_v0_miss_param_residual_stress import build


def test_miss_param_residual_slice_is_targeted_and_non_overlapping():
    payload = build()
    plan = payload["plan"]
    manifest = payload["manifest"]
    proof = payload["proof"]
    assert plan["blockers"] == []
    assert plan["selected_case_count"] == 68
    assert manifest["case_count_by_category"]["multi_turn_miss_param"] == 36
    assert proof["overlap_count"] == 0
    assert manifest["performance_evidence"] is False
    assert manifest["holdout_touched"] is False
    assert manifest["full_suite_touched"] is False


def test_miss_param_slot_recovery_spec_stays_compact_and_not_rule():
    payload = build()
    spec = payload["spec"]
    assert spec["mechanism_id"] == "missing_param_slot_recovery_controller_v1"
    assert spec["candidate_jsonl_generated"] is False
    assert spec["candidate_rule_generated"] is False
    assert spec["candidate_yaml_generated"] is False
    assert spec["activation_boundary"]["bfcl_category_specific_trigger_rule"] is False
    assert spec["activation_boundary"]["case_identifier_allowlist"] is False
    assert "call_prerequisite_lookup_tool_when_slot_is_tool_recoverable" in spec["controller_contract"]
