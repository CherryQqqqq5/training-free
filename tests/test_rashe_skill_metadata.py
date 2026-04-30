import json
import subprocess
import sys
from pathlib import Path

from grc.skills.router import SkillRouter
from grc.skills.store import SkillStore
from grc.skills.trace_buffer import find_path_indicators

SCRIPT = Path("scripts/check_rashe_skill_metadata.py")
REQUIRED_FORBIDDEN_SOURCE_LABELS = {
    "raw_case_identifier",
    "raw_trace_text",
    "raw_provider_payload",
    "gold",
    "expected",
    "scorer_diff",
    "candidate_output",
    "repair_output",
    "holdout_feedback",
    "full_suite_feedback",
}


def metadata():
    store = SkillStore.load_manifest()
    assert store.blockers == []
    return {
        skill_id: {
            "scope": skill.scope,
            "trigger_priority": skill.trigger_priority,
            "max_injection_tokens": skill.max_injection_tokens,
            "conflicts_with": list(skill.conflicts_with),
            "requires_schema": skill.requires_schema,
            "requires_current_turn": skill.requires_current_turn,
            "forbidden_sources": list(skill.forbidden_sources),
            "evaluation_status": skill.evaluation_status,
        }
        for skill_id, skill in store.skills.items()
    }


def step_trace_v0_2(**overrides):
    trace = {
        "skill_tags": ["bfcl_current_turn_focus"],
        "action_shape": "tool_call_boundary",
        "source_scope": "synthetic",
        "state_signature": "state:current-turn",
        "category": "synthetic_router_v0_2",
    }
    trace.update(overrides)
    return trace


def test_seed_skill_metadata_fields_complete_and_disabled():
    store = SkillStore.load_manifest()
    assert len(store.skills) == 4
    for skill in store.skills.values():
        assert skill.scope == "bfcl_offline_skeleton_seed"
        assert isinstance(skill.trigger_priority, int)
        assert skill.max_injection_tokens == 0
        assert isinstance(skill.conflicts_with, tuple)
        assert isinstance(skill.requires_schema, bool)
        assert isinstance(skill.requires_current_turn, bool)
        assert set(skill.forbidden_sources) == REQUIRED_FORBIDDEN_SOURCE_LABELS
        assert find_path_indicators({"forbidden_sources": list(skill.forbidden_sources)}) == []
        assert skill.evaluation_status == "offline_seed_validated"
        assert skill.enabled is False
        assert skill.runtime_authorized is False


def test_priority_ordering_selects_single_eligible_skill_fail_closed():
    decision = SkillRouter(skill_metadata=metadata()).route({"signals": ["current_turn", "memory_tool_visible"]})
    assert decision.decision_status == "selected"
    assert decision.selected_skill_id == "bfcl_current_turn_focus"
    assert decision.runtime_authorized is False
    assert decision.provider_call_count == 0
    assert decision.scorer_call_count == 0
    assert decision.source_collection_call_count == 0


def test_router_accepts_step_trace_v0_2_without_signals():
    decision = SkillRouter(skill_metadata=metadata()).route(step_trace_v0_2())
    assert decision.decision_status == "selected"
    assert decision.selected_skill_id == "bfcl_current_turn_focus"
    assert decision.runtime_authorized is False
    assert decision.provider_call_count == 0
    assert decision.scorer_call_count == 0
    assert decision.source_collection_call_count == 0


def test_router_accepts_approved_compact_step_trace_v0_2_without_signals():
    decision = SkillRouter(skill_metadata=metadata()).route(
        step_trace_v0_2(
            skill_tags=["bfcl_schema_reading"],
            action_shape="schema_lookup_boundary",
            source_scope="approved_compact",
            state_signature="state:schema-present",
            category="synthetic_schema_router_v0_2",
        )
    )
    assert decision.decision_status == "selected"
    assert decision.selected_skill_id == "bfcl_schema_reading"


def test_router_rejects_disabled_or_unknown_source_scope_before_route():
    for source_scope, reason in [("dev_only_future", "dev_only_future_scope_disabled"), ("raw_live_trace", "source_scope_not_allowed")]:
        decision = SkillRouter(skill_metadata=metadata()).route(step_trace_v0_2(source_scope=source_scope))
        assert decision.decision_status == "input_reject"
        assert decision.reject_reason == reason
        assert decision.selected_skill_id is None


def test_router_rejects_nonzero_call_counts_before_route():
    for field in ["provider_call_count", "scorer_call_count", "source_collection_call_count"]:
        decision = SkillRouter(skill_metadata=metadata()).route(step_trace_v0_2(**{field: 1}))
        assert decision.decision_status == "input_reject"
        assert decision.reject_reason == "call_count_nonzero"
        assert decision.selected_skill_id is None
        assert decision.provider_call_count == 0
        assert decision.scorer_call_count == 0
        assert decision.source_collection_call_count == 0
        assert decision.rejected_call_count_fields == (field,)
        decision_payload = decision.to_dict()
        assert decision_payload["rejected_call_count_fields"] == [field]


def test_router_rejects_raw_case_id_raw_trace_and_provider_payload_indicators():
    cases = [
        ({"case_id": "raw-case"}, "raw_case_id"),
        ({"diagnostic_path": "raw_trace://not-allowed"}, "path_indicator"),
        ({"provider_payload_path": "provider://not-called"}, "path_indicator"),
    ]
    for extra, reason in cases:
        decision = SkillRouter(skill_metadata=metadata()).route(step_trace_v0_2(**extra))
        assert decision.decision_status == "input_reject"
        assert decision.reject_reason == reason


def test_same_priority_ambiguity_rejects():
    meta = metadata()
    meta["bfcl_current_turn_focus"]["trigger_priority"] = 10
    meta["bfcl_memory_web_search_discipline"]["trigger_priority"] = 10
    decision = SkillRouter(skill_metadata=meta).route({"signals": ["current_turn", "memory_tool_visible"]})
    assert decision.decision_status == "ambiguous_reject"
    assert decision.reject_reason == "same_priority_skill_match"


def test_conflicts_with_rejects_before_selection():
    decision = SkillRouter(skill_metadata=metadata()).route({"signals": ["schema_present", "tool_like_payload"]})
    assert decision.decision_status == "conflict_reject"
    assert decision.reject_reason == "skill_conflict"


def test_schema_requirement_rejects_when_schema_signal_missing():
    decision = SkillRouter(skill_metadata=metadata()).route({"signals": ["argument_name_choice"]})
    assert decision.decision_status == "requirement_reject"
    assert decision.reject_reason == "schema_requirement_missing"


def test_current_turn_requirement_rejects_when_current_turn_missing():
    meta = metadata()
    meta["bfcl_memory_web_search_discipline"]["requires_current_turn"] = True
    decision = SkillRouter(skill_metadata=meta).route({"signals": ["memory_tool_visible"]})
    assert decision.decision_status == "requirement_reject"
    assert decision.reject_reason == "current_turn_requirement_missing"


def test_authorized_runtime_or_prompt_injection_rejects():
    for kwargs in [
        {"enabled": True},
        {"runtime_behavior_authorized": True},
        {"prompt_injection_authorized": True},
    ]:
        decision = SkillRouter(skill_metadata=metadata(), **kwargs).route({"signals": ["current_turn"]})
        assert decision.decision_status == "authorization_reject"
        assert decision.reject_reason == "runtime_behavior_not_authorized"


def test_skill_metadata_checker_compact_report_passes():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["rashe_skill_metadata_passed"] is True
    assert summary["skill_metadata_complete_count"] == 4
    assert summary["priority_ordering_checked"] == 1
    assert summary["conflict_reject_count"] == 1
    assert summary["schema_requirement_reject_count"] == 1
    assert summary["current_turn_requirement_reject_count"] == 1
    assert summary["ambiguity_reject_count"] == 1
    assert summary["forbidden_source_taxonomy_label_count"] == 10
    assert summary["step_trace_v0_2_route_checked"] == 1
    assert summary["step_trace_source_scope_reject_count"] == 2
    assert summary["call_count_nonzero_reject_count"] == 3
    assert summary["step_trace_call_count_reject_count"] == 3
    assert summary["rejected_call_count_fields_seen"] == ["provider_call_count", "scorer_call_count", "source_collection_call_count"]
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
    assert summary["candidate_generation_authorized"] is False
    assert summary["performance_evidence"] is False
