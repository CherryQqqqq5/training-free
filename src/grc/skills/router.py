"""Deterministic, default-disabled RASHE skill router."""

from __future__ import annotations

from typing import Any, Iterable

from .schema import RouterDecision

SIGNAL_TO_SKILL_GROUPS: tuple[tuple[set[str], str], ...] = (
    ({"multi_turn", "current_turn"}, "bfcl_current_turn_focus"),
    ({"malformed_tool_call_json", "no_tool_call", "tool_like_payload"}, "bfcl_tool_call_format_guard"),
    ({"schema_present", "required_properties", "argument_name_choice"}, "bfcl_schema_reading"),
    ({"memory_tool_visible", "web_search_tool_visible", "external_search_not_required"}, "bfcl_memory_web_search_discipline"),
)


class SkillRouter:
    """Inert router that only returns compact decisions for sanitized traces."""

    def __init__(self, *, enabled: bool = False, runtime_behavior_authorized: bool = False) -> None:
        self.enabled = enabled
        self.runtime_behavior_authorized = runtime_behavior_authorized

    def route(self, trace: dict[str, Any]) -> RouterDecision:
        if self.enabled or self.runtime_behavior_authorized:
            return RouterDecision(None, "authorization_reject", "runtime_behavior_not_authorized")
        if trace.get("ambiguous") is True:
            return RouterDecision(None, "ambiguous_reject", "ambiguous_skill_match")
        signals = _signals(trace.get("signals") or [])
        matches: list[str] = []
        for signal_group, skill_id in SIGNAL_TO_SKILL_GROUPS:
            if signal_group & signals:
                matches.append(skill_id)
        unique_matches = sorted(set(matches))
        if len(unique_matches) > 1:
            return RouterDecision(None, "ambiguous_reject", "ambiguous_skill_match")
        if not unique_matches:
            return RouterDecision(None, "no_match_reject", "no_skill_match")
        return RouterDecision(unique_matches[0], "selected", None)


def _signals(values: Iterable[Any]) -> set[str]:
    return {str(value) for value in values}


def route_trace(trace: dict[str, Any]) -> dict[str, Any]:
    return SkillRouter().route(trace).to_dict()
