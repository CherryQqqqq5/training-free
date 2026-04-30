import json
import subprocess
import sys
from pathlib import Path

from grc.skills.router import SkillRouter
from grc.skills.store import SkillStore

SCRIPT = Path("scripts/check_rashe_skill_metadata.py")


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
        assert skill.forbidden_sources
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
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
    assert summary["candidate_generation_authorized"] is False
    assert summary["performance_evidence"] is False
