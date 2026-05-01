import json
import sys
from pathlib import Path

import pytest

from grc.skills.router import SkillRouter, route_trace
from grc.skills.schema import find_forbidden_fields
from grc.skills.verifier import load_simple_yaml, verify_runtime_config, verify_trace

CONFIG = Path("configs/runtime_bfcl_skills.yaml")
APPROVAL_ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")
RUNTIME_PACKET = APPROVAL_ROOT / "rashe_runtime_behavior_approval_packet.json"
DOWNSTREAM_PACKETS = {
    "source": APPROVAL_ROOT / "rashe_source_real_trace_approval_packet.json",
    "candidate": APPROVAL_ROOT / "rashe_candidate_proposer_execution_approval_packet.json",
    "scorer": APPROVAL_ROOT / "rashe_scorer_dev_holdout_full_approval_packet.json",
    "performance": APPROVAL_ROOT / "rashe_performance_3pp_huawei_acceptance_approval_packet.json",
}
COMPACT_DECISION_KEYS = {
    "schema_version",
    "offline_only",
    "enabled",
    "runtime_authorized",
    "selected_skill_id",
    "decision_status",
    "reject_reason",
    "provider_call_count",
    "scorer_call_count",
    "source_collection_call_count",
    "rejected_call_count_fields",
}


def _synthetic_trace(**overrides):
    trace = {
        "trace_id": "synthetic-default-disabled",
        "trace_hash": "sha256:synthetic-default-disabled",
        "category": "synthetic_router_v0_2",
        "step_index": 0,
        "state_signature": "state:current-turn",
        "action_shape": "tool_call_boundary",
        "outcome_local": "compact_decision_only",
        "skill_tags": ["bfcl_current_turn_focus"],
        "source_scope": "synthetic",
        "signals": ["current_turn"],
        "offline_only": True,
        "synthetic_fixture": True,
        "provider_call_count": 0,
        "source_collection_call_count": 0,
        "scorer_call_count": 0,
        "candidate_call_count": 0,
    }
    trace.update(overrides)
    return trace


def _assert_zero_runtime_decision(decision):
    assert decision.offline_only is True
    assert decision.enabled is False
    assert decision.runtime_authorized is False
    assert decision.provider_call_count == 0
    assert decision.source_collection_call_count == 0
    assert decision.scorer_call_count == 0
    assert not hasattr(decision, "candidate_call_count")
    assert decision.to_dict()["provider_call_count"] == 0
    assert decision.to_dict()["source_collection_call_count"] == 0
    assert decision.to_dict()["scorer_call_count"] == 0
    assert "candidate_call_count" not in decision.to_dict()


def _assert_reject(decision, reason):
    assert decision.selected_skill_id is None
    assert decision.reject_reason == reason
    _assert_zero_runtime_decision(decision)


def _read_json(path: Path):
    return json.loads(path.read_text())


def test_runtime_config_default_disabled_and_zero_counters():
    config = load_simple_yaml(CONFIG)
    assert config["enabled"] is False
    assert config["runtime_behavior_authorized"] is False
    assert config["provider_calls_authorized"] is False
    assert config["source_collection_authorized"] is False
    assert config["scorer_authorized"] is False
    assert config["candidate_generation_authorized"] is False
    assert config["ruleengine_proxy_active_path_import_allowed"] is False
    assert config["provider_call_count"] == 0
    assert config["source_collection_call_count"] == 0
    assert config["scorer_call_count"] == 0
    assert config["candidate_call_count"] == 0

    report = verify_runtime_config(config)
    assert report.verifier_passed is True
    assert report.provider_call_count == 0
    assert report.source_collection_call_count == 0
    assert report.scorer_call_count == 0
    assert report.candidate_generation_authorized is False


def test_synthetic_default_disabled_router_emits_compact_decision_only():
    decision = SkillRouter().route(_synthetic_trace())
    assert decision.decision_status == "selected"
    assert decision.selected_skill_id == "bfcl_current_turn_focus"
    assert decision.reject_reason is None
    _assert_zero_runtime_decision(decision)
    payload = decision.to_dict()
    assert set(payload) == COMPACT_DECISION_KEYS
    assert payload["schema_version"] == "rashe_router_decision_v0"

    no_match = SkillRouter().route(_synthetic_trace(signals=[], skill_tags=[], action_shape="noop", state_signature="state:none"))
    assert no_match.decision_status == "no_match_reject"
    _assert_reject(no_match, "no_skill_match")


def test_ambiguous_routing_fails_closed_with_stable_reason():
    decision = SkillRouter().route(
        _synthetic_trace(
            signals=["current_turn", "schema_present"],
            skill_tags=["bfcl_current_turn_focus", "bfcl_schema_reading"],
            action_shape="tool_call_boundary",
        )
    )
    assert decision.decision_status == "ambiguous_reject"
    _assert_reject(decision, "ambiguous_skill_match")


@pytest.mark.parametrize(
    ("extra", "reason"),
    [
        ({"case_id": "raw-case-id"}, "raw_case_id"),
        ({"diagnostic_path": "outputs/bfcl_runs/raw_trace.json"}, "path_indicator"),
        ({"gold": "hidden"}, "forbidden_field"),
        ({"expected": "hidden"}, "forbidden_field"),
        ({"reference": "hidden"}, "forbidden_field"),
        ({"scorer_diff": "hidden"}, "forbidden_field"),
        ({"feedback": "hidden"}, "forbidden_field"),
        ({"candidate_output": "hidden"}, "forbidden_field"),
        ({"repair_output": "hidden"}, "forbidden_field"),
        ({"holdout_feedback": "hidden"}, "forbidden_field"),
        ({"full_suite_feedback": "hidden"}, "forbidden_field"),
    ],
)
def test_forbidden_leakage_fields_fail_closed(extra, reason):
    trace = _synthetic_trace(**extra)
    forbidden = find_forbidden_fields(trace)
    assert forbidden

    decision = SkillRouter().route(trace)
    assert decision.decision_status == "input_reject"
    _assert_reject(decision, reason)

    report = verify_trace(trace)
    assert report.verifier_passed is False
    assert "forbidden_fields_present" in report.blockers
    assert report.forbidden_field_violation_count > 0
    assert report.provider_call_count == 0
    assert report.source_collection_call_count == 0
    assert report.scorer_call_count == 0


def test_downstream_lanes_remain_pending_and_unauthorized():
    runtime_packet = _read_json(RUNTIME_PACKET)
    assert runtime_packet["approval_status"] == "approved"
    assert runtime_packet["runtime_behavior_authorized"] is True
    assert runtime_packet["runtime_behavior_scope"] == "synthetic_default_disabled_only"
    assert runtime_packet["provider_calls_authorized"] is False
    assert runtime_packet["source_collection_authorized"] is False
    assert runtime_packet["candidate_generation_authorized"] is False
    assert runtime_packet["scorer_authorized"] is False
    assert runtime_packet["performance_evidence"] is False
    assert runtime_packet["huawei_acceptance_ready"] is False

    for lane, path in DOWNSTREAM_PACKETS.items():
        packet = _read_json(path)
        assert packet["approval_status"] == "pending", lane
        assert packet["authorized"] is False, lane
        assert packet["source_collection_authorized"] is False, lane
        assert packet["candidate_generation_authorized"] is False, lane
        assert packet["scorer_authorized"] is False, lane
        assert packet["performance_evidence"] is False, lane
        assert packet["huawei_acceptance_ready"] is False, lane


def test_default_disabled_does_not_activate_ruleengine_or_real_bfcl_runtime():
    for module_name in list(sys.modules):
        if module_name == "grc.runtime" or module_name.startswith("grc.runtime."):
            del sys.modules[module_name]

    selected = SkillRouter().route(_synthetic_trace())
    reject_payload = route_trace(_synthetic_trace(signals=[], skill_tags=[], action_shape="noop", state_signature="state:none"))
    _assert_zero_runtime_decision(selected)
    assert reject_payload["decision_status"] == "no_match_reject"
    assert reject_payload["provider_call_count"] == 0
    assert reject_payload["source_collection_call_count"] == 0
    assert reject_payload["scorer_call_count"] == 0
    assert not any(name == "grc.runtime" or name.startswith("grc.runtime.") for name in sys.modules)

    for kwargs in [
        {"enabled": True},
        {"runtime_behavior_authorized": True},
        {"prompt_injection_authorized": True},
    ]:
        decision = SkillRouter(**kwargs).route(_synthetic_trace())
        assert decision.decision_status == "authorization_reject"
        _assert_reject(decision, "runtime_behavior_not_authorized")
