"""Schemas and safety helpers for the inert RASHE runtime skeleton."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

EXPECTED_SKILL_IDS = {
    "bfcl_current_turn_focus",
    "bfcl_schema_reading",
    "bfcl_tool_call_format_guard",
    "bfcl_memory_web_search_discipline",
}

FORBIDDEN_FIELD_NAMES = {
    "gold",
    "expected",
    "answer",
    "ground_truth",
    "oracle",
    "checker",
    "reference",
    "possible_answer",
    "score",
    "scorer_diff",
    "candidate",
    "candidate_output",
    "repair",
    "case_id",
}

PATH_INDICATORS = (
    "provider://",
    "scorer://",
    "source_collection://",
    "/provider/",
    "/scorer/",
    "/source_collection/",
    "outputs/bfcl_runs",
    "raw_trace",
    "raw_response_capture",
)


@dataclass(frozen=True)
class Skill:
    skill_id: str
    display_name: str
    allowed_triggers: tuple[str, ...]
    forbidden_triggers: tuple[str, ...]
    actions: tuple[str, ...]
    enabled: bool = False
    offline_only: bool = True
    runtime_authorized: bool = False
    schema_version: str = "rashe_skill_v0"


@dataclass(frozen=True)
class StepTrace:
    trace_id: str
    signals: tuple[str, ...]
    case_hash: str | None = None
    offline_only: bool = True
    synthetic_fixture: bool = True
    provider_call_count: int = 0
    scorer_call_count: int = 0
    source_collection_call_count: int = 0


@dataclass(frozen=True)
class RouterDecision:
    selected_skill_id: str | None
    decision_status: str
    reject_reason: str | None
    offline_only: bool = True
    enabled: bool = False
    runtime_authorized: bool = False
    provider_call_count: int = 0
    scorer_call_count: int = 0
    source_collection_call_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "rashe_router_decision_v0",
            "offline_only": self.offline_only,
            "enabled": self.enabled,
            "runtime_authorized": self.runtime_authorized,
            "selected_skill_id": self.selected_skill_id,
            "decision_status": self.decision_status,
            "reject_reason": self.reject_reason,
            "provider_call_count": self.provider_call_count,
            "scorer_call_count": self.scorer_call_count,
            "source_collection_call_count": self.source_collection_call_count,
        }


@dataclass(frozen=True)
class VerifierReport:
    verifier_passed: bool
    blockers: tuple[str, ...] = field(default_factory=tuple)
    forbidden_field_violation_count: int = 0
    path_indicator_violation_count: int = 0
    raw_case_id_rejected_count: int = 0
    case_hash_allowed_count: int = 0
    provider_call_count: int = 0
    scorer_call_count: int = 0
    source_collection_call_count: int = 0
    candidate_generation_authorized: bool = False
    offline_only: bool = True
    enabled: bool = False
    runtime_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "rashe_verifier_report_v0",
            "offline_only": self.offline_only,
            "enabled": self.enabled,
            "runtime_authorized": self.runtime_authorized,
            "candidate_generation_authorized": self.candidate_generation_authorized,
            "provider_call_count": self.provider_call_count,
            "scorer_call_count": self.scorer_call_count,
            "source_collection_call_count": self.source_collection_call_count,
            "forbidden_field_violation_count": self.forbidden_field_violation_count,
            "path_indicator_violation_count": self.path_indicator_violation_count,
            "raw_case_id_rejected_count": self.raw_case_id_rejected_count,
            "case_hash_allowed_count": self.case_hash_allowed_count,
            "verifier_passed": self.verifier_passed,
            "blockers": list(self.blockers),
        }


def find_forbidden_fields(obj: Any, path: str = "") -> list[str]:
    """Return forbidden field/path hits without inspecting external resources."""
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            key_s = str(key)
            key_l = key_s.lower()
            next_path = f"{path}.{key_s}" if path else key_s
            if key_l in FORBIDDEN_FIELD_NAMES:
                hits.append(next_path)
            hits.extend(find_forbidden_fields(value, next_path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            hits.extend(find_forbidden_fields(value, f"{path}[{index}]"))
    elif isinstance(obj, str):
        value_l = obj.lower()
        for indicator in PATH_INDICATORS:
            if indicator in value_l:
                hits.append(path or "<string>")
                break
    return hits


def has_raw_case_id(obj: Any) -> bool:
    return any(hit.endswith("case_id") or hit == "case_id" for hit in find_forbidden_fields(obj))
