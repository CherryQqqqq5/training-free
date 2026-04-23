from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable


class FailureStage(str, Enum):
    PRE_TOOL = "PRE_TOOL"
    MID_TOOL = "MID_TOOL"
    POST_TOOL = "POST_TOOL"


class FailureType(str, Enum):
    EMPTY_TOOL_CALL = "EMPTY_TOOL_CALL"
    ACTIONABLE_NO_TOOL_DECISION = "ACTIONABLE_NO_TOOL_DECISION"
    POST_TOOL_PROSE_SUMMARY = "POST_TOOL_PROSE_SUMMARY"
    TERMINATION_INADMISSIBLE = "TERMINATION_INADMISSIBLE"
    MALFORMED_CALL = "MALFORMED_CALL"
    ARG_UNDERSPECIFIED = "ARG_UNDERSPECIFIED"
    CLARIFICATION_REQUEST = "CLARIFICATION_REQUEST"
    UNSUPPORTED_REQUEST = "UNSUPPORTED_REQUEST"


_FILE_LITERAL_RE = re.compile(r"\b[\w.-]+\.[A-Za-z0-9]{1,8}\b")
_PATH_TOKEN_RE = re.compile(r"\b(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)\b")
_QUOTED_LITERAL_RE = re.compile(r"'([^']+)'|\"([^\"]+)\"")
_ID_TOKEN_RE = re.compile(r"\b(?:id|key|uuid|ticket|case|file|path)[_:\-\s]+([A-Za-z0-9_.:/-]{3,})\b", re.IGNORECASE)
_CLARIFICATION_RE = re.compile(
    r"\b(?:provide|confirm|specify|share|clarify|tell me|let me know|which|what|where)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FailureClassification:
    stage: FailureStage
    failure_type: FailureType
    error_type: str
    request_predicates: list[str] = field(default_factory=list)
    predicate_evidence: dict[str, bool] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"({self.stage.value},{self.failure_type.value})"


def collect_text_strings(value: Any) -> list[str]:
    strings: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, str):
            if item.strip():
                strings.append(item)
            return
        if isinstance(item, list):
            for child in item:
                visit(child)
            return
        if not isinstance(item, dict):
            return
        role = item.get("role")
        item_type = item.get("type")
        if role in {"developer", "system"}:
            return
        if item_type in {"function_call", "function_call_output"}:
            for key in ("arguments", "output", "content"):
                if key in item:
                    visit(item.get(key))
            return
        if role in {"user", "assistant", "tool"}:
            visit(item.get("content"))
            return
        for key, child in item.items():
            if key in {"role", "type", "name", "id", "call_id"}:
                continue
            visit(child)

    visit(value)
    return strings


def extract_sufficient_literals(value: Any) -> list[str]:
    literals: list[str] = []

    def add_literal(raw: str | None) -> None:
        if not raw:
            return
        cleaned = raw.strip()
        if cleaned and cleaned not in literals:
            literals.append(cleaned)

    for text in collect_text_strings(value):
        for token in _PATH_TOKEN_RE.findall(text):
            add_literal(token)
        for token in _FILE_LITERAL_RE.findall(text):
            add_literal(token)
        for match in _QUOTED_LITERAL_RE.finditer(text):
            add_literal(match.group(1) or match.group(2))
        for match in _ID_TOKEN_RE.finditer(text):
            add_literal(match.group(1))
    return literals


def has_sufficient_literals(value: Any, explicit_literals: Iterable[str] | None = None) -> bool:
    if explicit_literals is not None:
        return any(str(item).strip() for item in explicit_literals)
    return bool(extract_sufficient_literals(value))


def tool_output_sufficient(value: Any) -> bool:
    def visit(item: Any) -> bool:
        if isinstance(item, list):
            return any(visit(child) for child in item)
        if not isinstance(item, dict):
            return False
        if item.get("role") == "tool" or item.get("type") == "function_call_output":
            output = item.get("content", item.get("output"))
            if isinstance(output, str):
                return bool(output.strip())
            return output is not None
        return any(visit(child) for key, child in item.items() if key not in {"id", "call_id", "name"})

    return visit(value)


def is_clarification(content: Any) -> bool:
    if not isinstance(content, str):
        return False
    text = content.strip()
    if "?" not in text:
        return False
    return bool(_CLARIFICATION_RE.search(text))


def no_tool_predicates(
    *,
    tools_available: bool,
    literal_evidence: bool,
    tool_output_evidence: bool,
) -> list[str]:
    predicates: list[str] = []
    if tools_available:
        predicates.append("tools_available")
    if literal_evidence:
        predicates.append("prior_explicit_literals_present")
    if tool_output_evidence:
        predicates.append("prior_tool_outputs_present")
    return predicates


def classify_no_tool_failure(
    *,
    base_kind: str | None,
    content: Any,
    tools_available: bool,
    literal_evidence: bool,
    tool_output_evidence: bool,
    redundant_clarification_detected: bool = False,
) -> FailureClassification:
    predicates = no_tool_predicates(
        tools_available=tools_available,
        literal_evidence=literal_evidence,
        tool_output_evidence=tool_output_evidence,
    )
    evidence = {
        "has_sufficient_literals": literal_evidence,
        "tool_output_sufficient": tool_output_evidence,
        "is_clarification": is_clarification(content),
    }
    stage = FailureStage.POST_TOOL if tool_output_evidence else FailureStage.PRE_TOOL
    issue_kind = base_kind or "empty_tool_call"

    if issue_kind == "clarification_request":
        return FailureClassification(
            stage=stage,
            failure_type=FailureType.CLARIFICATION_REQUEST,
            error_type="redundant_clarification_request" if redundant_clarification_detected else "clarification_no_tool",
            request_predicates=predicates,
            predicate_evidence=evidence,
        )

    if issue_kind == "unsupported_request":
        return FailureClassification(
            stage=stage,
            failure_type=FailureType.UNSUPPORTED_REQUEST,
            error_type="unsupported_no_tool",
            request_predicates=predicates,
            predicate_evidence=evidence,
        )

    actionable_bases = {
        "empty_tool_call",
        "hallucinated_completion",
        "natural_language_termination",
        "malformed_output",
    }
    if issue_kind in actionable_bases and tools_available and (literal_evidence or tool_output_evidence):
        return FailureClassification(
            stage=stage,
            failure_type=FailureType.ACTIONABLE_NO_TOOL_DECISION,
            error_type="actionable_no_tool_decision",
            request_predicates=predicates,
            predicate_evidence=evidence,
        )

    return FailureClassification(
        stage=stage,
        failure_type=FailureType.EMPTY_TOOL_CALL,
        error_type=issue_kind,
        request_predicates=predicates,
        predicate_evidence=evidence,
    )


def classify_error_type(
    error_type: str,
    *,
    request_predicates: Iterable[str] | None = None,
    has_prior_tool_output: bool = False,
) -> FailureClassification:
    predicates = list(request_predicates or [])
    predicate_set = set(predicates)
    stage = FailureStage.POST_TOOL if has_prior_tool_output or "prior_tool_outputs_present" in predicate_set else FailureStage.MID_TOOL
    normalized = str(error_type or "validation_issue")

    if normalized == "post_tool_prose_summary":
        return FailureClassification(stage=FailureStage.POST_TOOL, failure_type=FailureType.POST_TOOL_PROSE_SUMMARY, error_type=normalized, request_predicates=predicates)
    if normalized == "termination_inadmissible":
        return FailureClassification(stage=stage, failure_type=FailureType.TERMINATION_INADMISSIBLE, error_type=normalized, request_predicates=predicates)
    if normalized == "actionable_no_tool_decision":
        no_tool_stage = FailureStage.POST_TOOL if "prior_tool_outputs_present" in predicate_set or has_prior_tool_output else FailureStage.PRE_TOOL
        return FailureClassification(stage=no_tool_stage, failure_type=FailureType.ACTIONABLE_NO_TOOL_DECISION, error_type=normalized, request_predicates=predicates)
    if normalized in {"empty_tool_call", "empty_completion", "hallucinated_completion", "natural_language_termination", "malformed_output"}:
        no_tool_stage = FailureStage.POST_TOOL if "prior_tool_outputs_present" in predicate_set or has_prior_tool_output else FailureStage.PRE_TOOL
        return FailureClassification(stage=no_tool_stage, failure_type=FailureType.EMPTY_TOOL_CALL, error_type=normalized, request_predicates=predicates)
    if normalized in {"clarification_request", "clarification_no_tool", "redundant_clarification_request"}:
        no_tool_stage = FailureStage.POST_TOOL if "prior_tool_outputs_present" in predicate_set or has_prior_tool_output else FailureStage.PRE_TOOL
        return FailureClassification(stage=no_tool_stage, failure_type=FailureType.CLARIFICATION_REQUEST, error_type=normalized, request_predicates=predicates)
    if normalized in {"unsupported_request", "unsupported_no_tool"}:
        no_tool_stage = FailureStage.POST_TOOL if "prior_tool_outputs_present" in predicate_set or has_prior_tool_output else FailureStage.PRE_TOOL
        return FailureClassification(stage=no_tool_stage, failure_type=FailureType.UNSUPPORTED_REQUEST, error_type=normalized, request_predicates=predicates)
    if normalized in {"missing_required"}:
        return FailureClassification(stage=FailureStage.MID_TOOL, failure_type=FailureType.ARG_UNDERSPECIFIED, error_type=normalized, request_predicates=predicates)
    if normalized in {"invalid_json_args", "non_object_args", "unknown_field", "type_mismatch", "wrong_tool_name"}:
        return FailureClassification(stage=FailureStage.MID_TOOL, failure_type=FailureType.MALFORMED_CALL, error_type=normalized, request_predicates=predicates)
    return FailureClassification(stage=stage, failure_type=FailureType.MALFORMED_CALL, error_type=normalized, request_predicates=predicates)
