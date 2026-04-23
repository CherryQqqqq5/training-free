from __future__ import annotations

from typing import Any

from grc.compiler.failure_taxonomy import FailureType


DECISION_LAYER_TYPES = {
    FailureType.ACTIONABLE_NO_TOOL_DECISION.value,
    FailureType.POST_TOOL_PROSE_SUMMARY.value,
    FailureType.TERMINATION_INADMISSIBLE.value,
}
COMPATIBILITY_HEAVY_TYPES = {
    FailureType.MALFORMED_CALL.value,
    FailureType.ARG_UNDERSPECIFIED.value,
    FailureType.EMPTY_TOOL_CALL.value,
}
ALLOWED_BOUNDARY_TYPES = {
    FailureType.CLARIFICATION_REQUEST.value,
    FailureType.UNSUPPORTED_REQUEST.value,
}


def failure_type_from_label(label: str) -> str:
    cleaned = str(label or "").strip().strip("()")
    if "," not in cleaned:
        return cleaned
    return cleaned.split(",", 1)[1].strip()


def group_failure_label(label: str, predicate_evidence: dict[str, Any] | None = None) -> str:
    failure_type = failure_type_from_label(label)
    evidence = predicate_evidence or {}
    if (
        failure_type == FailureType.CLARIFICATION_REQUEST.value
        and bool(evidence.get("prior_explicit_literals_present") or evidence.get("has_sufficient_literals"))
    ):
        return "boundary_misuse"
    if failure_type in DECISION_LAYER_TYPES:
        return "decision_layer_target"
    if failure_type in COMPATIBILITY_HEAVY_TYPES:
        return "compatibility_heavy"
    if failure_type in ALLOWED_BOUNDARY_TYPES:
        return "allowed_boundary"
    return "unknown"
