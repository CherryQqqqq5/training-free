"""Deterministic, default-disabled RASHE skill router."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from .schema import RouterDecision, find_forbidden_fields
from .trace_buffer import find_path_indicators

SIGNAL_TO_SKILL_GROUPS: tuple[tuple[set[str], str], ...] = (
    ({"multi_turn", "current_turn"}, "bfcl_current_turn_focus"),
    ({"malformed_tool_call_json", "no_tool_call", "tool_like_payload"}, "bfcl_tool_call_format_guard"),
    ({"schema_present", "required_properties", "argument_name_choice"}, "bfcl_schema_reading"),
    ({"memory_tool_visible", "web_search_tool_visible", "external_search_not_required"}, "bfcl_memory_web_search_discipline"),
)

SCHEMA_SIGNALS = {"schema_present", "required_properties"}
CURRENT_TURN_SIGNALS = {"current_turn", "multi_turn"}
ALLOWED_SOURCE_SCOPES = {"synthetic", "approved_compact"}
REJECTED_SOURCE_SCOPES = {"dev_only_future"}
CALL_COUNT_FIELDS = ("provider_call_count", "scorer_call_count", "source_collection_call_count")
SKILL_TAG_TO_SIGNAL = {
    "bfcl_current_turn_focus": "current_turn",
    "bfcl_schema_reading": "schema_present",
    "bfcl_tool_call_format_guard": "tool_like_payload",
    "bfcl_memory_web_search_discipline": "memory_tool_visible",
}
ACTION_SHAPE_TO_SIGNAL = {
    "tool_call_boundary": "current_turn",
    "schema_lookup_boundary": "schema_present",
    "tool_call_format_guard": "tool_like_payload",
    "memory_web_search_boundary": "memory_tool_visible",
}


class SkillRouter:
    """Inert router that only returns compact decisions for sanitized traces."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        runtime_behavior_authorized: bool = False,
        prompt_injection_authorized: bool = False,
        skill_metadata: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> None:
        self.enabled = enabled
        self.runtime_behavior_authorized = runtime_behavior_authorized
        self.prompt_injection_authorized = prompt_injection_authorized
        self.skill_metadata = skill_metadata

    def route(self, trace: dict[str, Any]) -> RouterDecision:
        if self.enabled or self.runtime_behavior_authorized or self.prompt_injection_authorized:
            return RouterDecision(None, "authorization_reject", "runtime_behavior_not_authorized")
        call_count_fields = _call_count_reject_fields(trace)
        if call_count_fields:
            return RouterDecision(None, "input_reject", "call_count_nonzero", rejected_call_count_fields=tuple(call_count_fields))
        preflight_reject = _preflight_reject(trace)
        if preflight_reject is not None:
            return RouterDecision(None, "input_reject", preflight_reject)
        if trace.get("ambiguous") is True:
            return RouterDecision(None, "ambiguous_reject", "ambiguous_skill_match")
        signals = _trace_signals(trace)
        matches = _matching_skills(signals)
        if self.skill_metadata is None:
            return _legacy_route(matches)
        return self._route_with_metadata(signals, matches)

    def _route_with_metadata(self, signals: set[str], matches: list[str]) -> RouterDecision:
        unique_matches = sorted(set(matches))
        if not unique_matches:
            return RouterDecision(None, "no_match_reject", "no_skill_match")
        missing = [skill_id for skill_id in unique_matches if skill_id not in self.skill_metadata]
        if missing:
            return RouterDecision(None, "metadata_reject", "skill_metadata_missing")
        for skill_id in unique_matches:
            metadata = self.skill_metadata[skill_id]
            if metadata.get("requires_schema") is True and not (signals & SCHEMA_SIGNALS):
                return RouterDecision(None, "requirement_reject", "schema_requirement_missing")
            if metadata.get("requires_current_turn") is True and not (signals & CURRENT_TURN_SIGNALS):
                return RouterDecision(None, "requirement_reject", "current_turn_requirement_missing")
        if _has_conflict(unique_matches, self.skill_metadata):
            return RouterDecision(None, "conflict_reject", "skill_conflict")
        ranked = sorted(unique_matches, key=lambda skill_id: (int(self.skill_metadata[skill_id].get("trigger_priority", 9999)), skill_id))
        best_priority = int(self.skill_metadata[ranked[0]].get("trigger_priority", 9999))
        top = [skill_id for skill_id in ranked if int(self.skill_metadata[skill_id].get("trigger_priority", 9999)) == best_priority]
        if len(top) > 1:
            return RouterDecision(None, "ambiguous_reject", "same_priority_skill_match")
        return RouterDecision(ranked[0], "selected", None)


def _call_count_reject_fields(trace: dict[str, Any]) -> list[str]:
    return [field for field in CALL_COUNT_FIELDS if field in trace and trace.get(field) != 0]


def _preflight_reject(trace: dict[str, Any]) -> str | None:
    source_scope = trace.get("source_scope")
    if source_scope is not None:
        if source_scope in REJECTED_SOURCE_SCOPES:
            return "dev_only_future_scope_disabled"
        if source_scope not in ALLOWED_SOURCE_SCOPES:
            return "source_scope_not_allowed"
    forbidden = find_forbidden_fields(trace)
    if any(hit.endswith("case_id") or hit == "case_id" for hit in forbidden):
        return "raw_case_id"
    if find_path_indicators(trace):
        return "path_indicator"
    if forbidden:
        return "forbidden_field"
    return None


def _trace_signals(trace: dict[str, Any]) -> set[str]:
    signals = _signals(trace.get("signals") or [])
    for tag in trace.get("skill_tags") or []:
        signal = SKILL_TAG_TO_SIGNAL.get(str(tag))
        if signal:
            signals.add(signal)
    action_signal = ACTION_SHAPE_TO_SIGNAL.get(str(trace.get("action_shape") or ""))
    if action_signal:
        signals.add(action_signal)
    state_signature = str(trace.get("state_signature") or "")
    category = str(trace.get("category") or "")
    if "schema" in state_signature or "schema" in category:
        signals.add("schema_present")
    if "current" in state_signature or "current" in category:
        signals.add("current_turn")
    return signals


def _matching_skills(signals: set[str]) -> list[str]:
    matches: list[str] = []
    for signal_group, skill_id in SIGNAL_TO_SKILL_GROUPS:
        if signal_group & signals:
            matches.append(skill_id)
    return matches


def _legacy_route(matches: list[str]) -> RouterDecision:
    unique_matches = sorted(set(matches))
    if len(unique_matches) > 1:
        return RouterDecision(None, "ambiguous_reject", "ambiguous_skill_match")
    if not unique_matches:
        return RouterDecision(None, "no_match_reject", "no_skill_match")
    return RouterDecision(unique_matches[0], "selected", None)


def _has_conflict(skill_ids: list[str], metadata: Mapping[str, Mapping[str, Any]]) -> bool:
    skill_set = set(skill_ids)
    for skill_id in skill_ids:
        conflicts = set(str(item) for item in metadata[skill_id].get("conflicts_with") or [])
        if conflicts & skill_set:
            return True
    return False


def _signals(values: Iterable[Any]) -> set[str]:
    return {str(value) for value in values}


def route_trace(trace: dict[str, Any]) -> dict[str, Any]:
    return SkillRouter().route(trace).to_dict()
