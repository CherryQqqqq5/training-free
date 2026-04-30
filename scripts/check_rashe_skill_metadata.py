#!/usr/bin/env python3
"""Offline checker for RASHE seed skill metadata and router gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from grc.skills.router import SkillRouter
from grc.skills.store import SkillStore

DEFAULT_MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/skillbank_manifest.json")
REQUIRED_METADATA_FIELDS = (
    "scope",
    "trigger_priority",
    "max_injection_tokens",
    "conflicts_with",
    "requires_schema",
    "requires_current_turn",
    "forbidden_sources",
    "evaluation_status",
)
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


def _metadata_from_store(store: SkillStore) -> dict[str, dict[str, Any]]:
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


def _metadata_blockers(metadata: dict[str, dict[str, Any]]) -> tuple[list[str], int]:
    blockers: list[str] = []
    complete = 0
    for skill_id, fields in metadata.items():
        before = len(blockers)
        missing = [key for key in REQUIRED_METADATA_FIELDS if key not in fields]
        if missing:
            blockers.append("skill_metadata_missing:" + skill_id + ":" + ",".join(missing))
            continue
        if not isinstance(fields["scope"], str) or not fields["scope"]:
            blockers.append(f"skill_scope_invalid:{skill_id}")
        if not isinstance(fields["trigger_priority"], int):
            blockers.append(f"skill_trigger_priority_invalid:{skill_id}")
        if fields["max_injection_tokens"] != 0:
            blockers.append(f"skill_max_injection_tokens_not_zero:{skill_id}")
        if not isinstance(fields["conflicts_with"], list):
            blockers.append(f"skill_conflicts_with_invalid:{skill_id}")
        if not isinstance(fields["requires_schema"], bool):
            blockers.append(f"skill_requires_schema_invalid:{skill_id}")
        if not isinstance(fields["requires_current_turn"], bool):
            blockers.append(f"skill_requires_current_turn_invalid:{skill_id}")
        if not isinstance(fields["forbidden_sources"], list) or not fields["forbidden_sources"]:
            blockers.append(f"skill_forbidden_sources_invalid:{skill_id}")
        elif set(fields["forbidden_sources"]) != REQUIRED_FORBIDDEN_SOURCE_LABELS:
            blockers.append(f"skill_forbidden_sources_taxonomy_invalid:{skill_id}")
        if fields["evaluation_status"] != "offline_seed_validated":
            blockers.append(f"skill_evaluation_status_invalid:{skill_id}")
        if len(blockers) == before:
            complete += 1
    return blockers, complete


def _with_priority(metadata: dict[str, dict[str, Any]], *updates: tuple[str, int]) -> dict[str, dict[str, Any]]:
    clone = {skill_id: dict(values) for skill_id, values in metadata.items()}
    for skill_id, priority in updates:
        clone[skill_id]["trigger_priority"] = priority
        clone[skill_id]["conflicts_with"] = []
    return clone


def _with_requirement(metadata: dict[str, dict[str, Any]], skill_id: str, key: str, value: bool) -> dict[str, dict[str, Any]]:
    clone = {sid: dict(values) for sid, values in metadata.items()}
    clone[skill_id][key] = value
    clone[skill_id]["conflicts_with"] = []
    return clone


def check(manifest: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    store = SkillStore.load_manifest(manifest)
    blockers = list(store.blockers)
    metadata = _metadata_from_store(store)
    metadata_blockers, complete_count = _metadata_blockers(metadata)
    blockers.extend(metadata_blockers)

    priority_ordering_checked = 0
    conflict_reject_count = 0
    schema_requirement_reject_count = 0
    current_turn_requirement_reject_count = 0
    ambiguity_reject_count = 0
    step_trace_v0_2_route_checked = 0
    step_trace_source_scope_reject_count = 0
    call_count_nonzero_reject_count = 0

    decision = SkillRouter(skill_metadata=metadata).route({"signals": ["current_turn", "memory_tool_visible"]})
    if decision.decision_status == "selected" and decision.selected_skill_id == "bfcl_current_turn_focus":
        priority_ordering_checked += 1
    else:
        blockers.append(f"priority_ordering_failed:{decision.decision_status}:{decision.selected_skill_id}:{decision.reject_reason}")

    same_priority_metadata = _with_priority(metadata, ("bfcl_current_turn_focus", 10), ("bfcl_memory_web_search_discipline", 10))
    decision = SkillRouter(skill_metadata=same_priority_metadata).route({"signals": ["current_turn", "memory_tool_visible"]})
    if decision.decision_status == "ambiguous_reject" and decision.reject_reason == "same_priority_skill_match":
        ambiguity_reject_count += 1
    else:
        blockers.append("same_priority_ambiguity_not_rejected")

    decision = SkillRouter(skill_metadata=metadata).route({"signals": ["schema_present", "tool_like_payload"]})
    if decision.decision_status == "conflict_reject" and decision.reject_reason == "skill_conflict":
        conflict_reject_count += 1
    else:
        blockers.append(f"conflict_not_rejected:{decision.decision_status}:{decision.reject_reason}")

    decision = SkillRouter(skill_metadata=metadata).route({"signals": ["argument_name_choice"]})
    if decision.decision_status == "requirement_reject" and decision.reject_reason == "schema_requirement_missing":
        schema_requirement_reject_count += 1
    else:
        blockers.append(f"schema_requirement_not_rejected:{decision.decision_status}:{decision.reject_reason}")

    current_req_metadata = _with_requirement(metadata, "bfcl_memory_web_search_discipline", "requires_current_turn", True)
    decision = SkillRouter(skill_metadata=current_req_metadata).route({"signals": ["memory_tool_visible"]})
    if decision.decision_status == "requirement_reject" and decision.reject_reason == "current_turn_requirement_missing":
        current_turn_requirement_reject_count += 1
    else:
        blockers.append(f"current_turn_requirement_not_rejected:{decision.decision_status}:{decision.reject_reason}")

    step_trace = {
        "skill_tags": ["bfcl_current_turn_focus"],
        "action_shape": "tool_call_boundary",
        "source_scope": "synthetic",
        "state_signature": "state:current-turn",
        "category": "synthetic_router_v0_2",
    }
    decision = SkillRouter(skill_metadata=metadata).route(step_trace)
    if decision.decision_status == "selected" and decision.selected_skill_id == "bfcl_current_turn_focus":
        step_trace_v0_2_route_checked += 1
    else:
        blockers.append(f"step_trace_v0_2_route_failed:{decision.decision_status}:{decision.reject_reason}")

    for source_scope, reason in [("dev_only_future", "dev_only_future_scope_disabled"), ("raw_live_trace", "source_scope_not_allowed")]:
        decision = SkillRouter(skill_metadata=metadata).route({**step_trace, "source_scope": source_scope})
        if decision.decision_status == "input_reject" and decision.reject_reason == reason:
            step_trace_source_scope_reject_count += 1
        else:
            blockers.append(f"step_trace_source_scope_not_rejected:{source_scope}:{decision.decision_status}:{decision.reject_reason}")

    for field in ["provider_call_count", "scorer_call_count", "source_collection_call_count"]:
        decision = SkillRouter(skill_metadata=metadata).route({**step_trace, field: 1})
        if decision.decision_status == "input_reject" and decision.reject_reason == "call_count_nonzero":
            call_count_nonzero_reject_count += 1
        else:
            blockers.append(f"call_count_nonzero_not_rejected:{field}:{decision.decision_status}:{decision.reject_reason}")

    summary = {
        "report_scope": "rashe_skill_metadata_check",
        "offline_only": True,
        "enabled": False,
        "runtime_behavior_authorized": False,
        "prompt_injection_authorized": False,
        "retry_authorized": False,
        "candidate_generation_authorized": False,
        "performance_evidence": False,
        "skill_metadata_complete_count": complete_count,
        "skill_count": len(metadata),
        "priority_ordering_checked": priority_ordering_checked,
        "conflict_reject_count": conflict_reject_count,
        "schema_requirement_reject_count": schema_requirement_reject_count,
        "current_turn_requirement_reject_count": current_turn_requirement_reject_count,
        "ambiguity_reject_count": ambiguity_reject_count,
        "forbidden_source_taxonomy_label_count": len(REQUIRED_FORBIDDEN_SOURCE_LABELS),
        "step_trace_v0_2_route_checked": step_trace_v0_2_route_checked,
        "step_trace_source_scope_reject_count": step_trace_source_scope_reject_count,
        "call_count_nonzero_reject_count": call_count_nonzero_reject_count,
        "step_trace_call_count_reject_count": call_count_nonzero_reject_count,
        "provider_call_count": 0,
        "scorer_call_count": 0,
        "source_collection_call_count": 0,
        "rashe_skill_metadata_passed": not blockers,
        "blockers": blockers,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--compact", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    summary = check(args.manifest)
    print(json.dumps(summary, sort_keys=True) if args.compact else json.dumps(summary, indent=2, sort_keys=True))
    if args.strict and not summary["rashe_skill_metadata_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
