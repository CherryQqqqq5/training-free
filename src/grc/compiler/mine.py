from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable, List

from grc.compiler.failure_taxonomy import (
    FailureClassification,
    classify_error_type,
    classify_no_tool_failure,
)
from grc.compiler.action_candidates import generate_action_candidates
from grc.compiler.failure_signature import tool_schema_hash
from grc.compiler.tool_state import extract_tool_state
from grc.types import FailureCase
from grc.utils.jsonfix import parse_loose_json
from grc.utils.text_tool_calls import (
    classify_no_tool_call_content,
    parse_text_tool_calls,
)
from grc.utils.tool_schema import normalize_tool_schema_snapshot, tool_map_from_tools_payload

_FUNCTION_LIST_MARKER_RE = re.compile(
    r"Here is a list of functions in json format that you can invoke\.\n(\[.*\])\s*$",
    re.DOTALL,
)
_FILE_LITERAL_RE = re.compile(r"\b[\w.-]+\.[A-Za-z0-9]{1,8}\b")
_QUOTED_LITERAL_RE = re.compile(r"'([^']+)'|\"([^\"]+)\"")
_REQUESTED_VALUE_RE = re.compile(
    r"(?:provide|confirm|specify|share|clarify|tell me|let me know)(?:\s+(?:the|which|what|a|an|specific))?\s+([^?.!,]+)",
    re.IGNORECASE,
)
_GENERIC_CONTEXT_TOKENS = {
    "information",
    "details",
    "detail",
    "value",
    "parameter",
    "parameters",
    "input",
    "inputs",
    "required",
    "missing",
    "needed",
    "available",
    "specific",
    "please",
    "before",
}
_FILE_CONTEXT_HINT_RE = re.compile(r"\b(file|filename|document|report)\b", re.IGNORECASE)
_PATH_CONTEXT_HINT_RE = re.compile(r"\b(directory|folder|path)\b", re.IGNORECASE)
_PATH_TOKEN_RE = re.compile(r"\b(?:[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+)\b")

def _extract_tools_from_prompt_text(text: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(text, str):
        return {}

    match = _FUNCTION_LIST_MARKER_RE.search(text)
    if not match:
        return {}

    try:
        functions = json.loads(match.group(1))
    except Exception:
        return {}

    return tool_map_from_tools_payload(functions)


def _tool_map_from_messages(messages: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(messages, list):
        return {}

    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        tool_map = _extract_tools_from_prompt_text(content)
        if tool_map:
            return tool_map

    return {}


def _tool_map_from_responses_input(input_value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(input_value, list):
        return {}

    for item in input_value:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if isinstance(content, str):
            tool_map = _extract_tools_from_prompt_text(content)
            if tool_map:
                return tool_map
            continue
        if isinstance(content, list):
            for chunk in content:
                if not isinstance(chunk, dict):
                    continue
                text = chunk.get("text") or chunk.get("content") or chunk.get("input_text")
                tool_map = _extract_tools_from_prompt_text(text)
                if tool_map:
                    return tool_map

    return {}


def _tool_schema_map(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    req = data.get("request", {})
    request_original = data.get("request_original", {})

    candidates = (
        normalize_tool_schema_snapshot(data.get("tool_schema_snapshot")),
        tool_map_from_tools_payload(req.get("tools") if isinstance(req, dict) else None),
        _tool_map_from_messages(req.get("messages") if isinstance(req, dict) else None),
        tool_map_from_tools_payload(request_original.get("tools") if isinstance(request_original, dict) else None),
        _tool_map_from_messages(request_original.get("messages") if isinstance(request_original, dict) else None),
        _tool_map_from_responses_input(request_original.get("input") if isinstance(request_original, dict) else None),
    )

    for tool_map in candidates:
        if tool_map:
            return tool_map

    return {}


def _python_matches_json_type(value: Any, expected: str) -> bool:
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def _collect_context_strings(value: Any) -> List[str]:
    strings: List[str] = []

    def visit(item: Any, *, parent_role: str | None = None) -> None:
        if isinstance(item, str):
            if item.strip():
                strings.append(item)
            return
        if isinstance(item, list):
            for child in item:
                visit(child, parent_role=parent_role)
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
                    visit(item.get(key), parent_role=role)
            return
        if role in {"user", "assistant", "tool"}:
            visit(item.get("content"), parent_role=role)
            return
        for key, value in item.items():
            if key in {"role", "type", "name", "id", "call_id"}:
                continue
            visit(value, parent_role=parent_role)

    visit(value)
    return strings


def _context_tokens(strings: Iterable[str]) -> set[str]:
    tokens: set[str] = set()
    for text in strings:
        for token in re.findall(r"[a-z0-9_./-]+", text.lower()):
            if len(token) <= 2 or token in _GENERIC_CONTEXT_TOKENS:
                continue
            tokens.add(token)
    return tokens


def _requested_value_tokens(content: str) -> set[str]:
    match = _REQUESTED_VALUE_RE.search(content)
    if not match:
        return set()
    phrase = match.group(1)
    return {
        token
        for token in re.findall(r"[a-z0-9_./-]+", phrase.lower())
        if len(token) > 2 and token not in _GENERIC_CONTEXT_TOKENS
    }


def _is_redundant_clarification_request(data: dict[str, Any], content: str) -> bool:
    if not isinstance(content, str) or not content.strip():
        return False

    context_strings = _collect_context_strings(
        [
            data.get("request", {}).get("messages"),
            data.get("request_original", {}).get("messages"),
            data.get("request_original", {}).get("input"),
        ]
    )
    if not context_strings:
        return False

    context_blob = "\n".join(context_strings)
    lowered = content.lower()
    if _FILE_CONTEXT_HINT_RE.search(lowered):
        if _FILE_LITERAL_RE.search(context_blob):
            return True
        if any(match.group(1) or match.group(2) for match in _QUOTED_LITERAL_RE.finditer(context_blob)):
            return True
    if _PATH_CONTEXT_HINT_RE.search(lowered):
        if any("/" in text or "\\" in text for text in context_strings):
            return True

    requested_tokens = _requested_value_tokens(content)
    if not requested_tokens:
        return False

    return bool(requested_tokens & _context_tokens(context_strings))


def _has_prior_tool_outputs(data: dict[str, Any]) -> bool:
    def visit(item: Any) -> bool:
        if isinstance(item, list):
            return any(visit(child) for child in item)
        if not isinstance(item, dict):
            return False
        if item.get("role") == "tool" or item.get("type") == "function_call_output":
            return True
        return any(visit(value) for key, value in item.items() if key not in {"id", "call_id", "name"})

    return any(
        visit(candidate)
        for candidate in (
            data.get("request", {}).get("messages"),
            data.get("request_original", {}).get("messages"),
            data.get("request_original", {}).get("input"),
        )
    )


def _explicit_context_literals(data: dict[str, Any]) -> list[str]:
    context_strings = _collect_context_strings(
        [
            data.get("request", {}).get("messages"),
            data.get("request_original", {}).get("messages"),
            data.get("request_original", {}).get("input"),
        ]
    )
    literals: list[str] = []

    def add_literal(value: str) -> None:
        cleaned = str(value).strip()
        if not cleaned or cleaned in literals:
            return
        literals.append(cleaned)

    for text in context_strings:
        for token in _PATH_TOKEN_RE.findall(text):
            add_literal(token)
        for token in _FILE_LITERAL_RE.findall(text):
            add_literal(token)
    return literals


def _request_local_no_tool_predicates(
    data: dict[str, Any],
    tool_map: dict[str, dict[str, Any]],
    *,
    explicit_literals: list[str] | None = None,
) -> list[str]:
    predicates: list[str] = []
    if tool_map:
        predicates.append("tools_available")
    if explicit_literals is None:
        explicit_literals = _explicit_context_literals(data)
    if explicit_literals:
        predicates.append("prior_explicit_literals_present")
    if _has_prior_tool_outputs(data):
        predicates.append("prior_tool_outputs_present")
    return predicates


def _schema_text_tokens(tool_name: str, schema: dict[str, Any]) -> set[str]:
    values: list[str] = [tool_name]

    def visit(item: Any) -> None:
        if isinstance(item, str):
            values.append(item)
            return
        if isinstance(item, list):
            for child in item:
                visit(child)
            return
        if isinstance(item, dict):
            for key, value in item.items():
                values.append(str(key))
                visit(value)

    visit(schema)
    return _context_tokens(values)


def _rank_recommended_tools(
    data: dict[str, Any],
    tool_map: dict[str, dict[str, Any]],
    explicit_literals: list[str],
) -> list[str]:
    if not tool_map:
        return []
    if len(tool_map) == 1:
        return list(tool_map.keys())

    context_strings = _collect_context_strings(
        [
            data.get("request", {}).get("messages"),
            data.get("request_original", {}).get("messages"),
            data.get("request_original", {}).get("input"),
            explicit_literals,
        ]
    )
    context_tokens = _context_tokens(context_strings)
    has_file_literal = any(_FILE_LITERAL_RE.search(item) for item in explicit_literals)
    has_path_literal = any("/" in item or "\\" in item for item in explicit_literals)

    scored: list[tuple[float, str]] = []
    for name, schema in tool_map.items():
        schema_tokens = _schema_text_tokens(name, schema)
        overlap = len(context_tokens & schema_tokens)
        literal_bonus = 0.0
        if has_file_literal and schema_tokens & {"file", "filename", "file_name", "path", "source", "destination"}:
            literal_bonus += 1.0
        if has_path_literal and schema_tokens & {"path", "directory", "folder", "dir"}:
            literal_bonus += 1.0
        score = float(overlap) + literal_bonus
        if score > 0:
            scored.append((score, name))

    return [name for _, name in sorted(scored, key=lambda item: (-item[0], item[1]))[:3]]


def _classify_no_tool_subfamily(
    data: dict[str, Any],
    base_kind: str | None,
    tool_map: dict[str, dict[str, Any]],
    *,
    explicit_literals: list[str] | None = None,
    redundant_clarification_detected: bool = False,
) -> tuple[str | None, list[str], FailureClassification]:
    predicates = _request_local_no_tool_predicates(data, tool_map, explicit_literals=explicit_literals)
    choices = data.get("raw_response", {}).get("choices", [])
    first_message = choices[0].get("message", {}) if isinstance(choices, list) and choices else {}
    classification = classify_no_tool_failure(
        base_kind=base_kind,
        content=first_message.get("content", ""),
        tools_available=bool(tool_map),
        literal_evidence="prior_explicit_literals_present" in predicates,
        tool_output_evidence="prior_tool_outputs_present" in predicates,
        redundant_clarification_detected=redundant_clarification_detected,
    )
    return classification.error_type, classification.request_predicates, classification


def mine_failures(trace_dir: str) -> List[FailureCase]:
    trace_root = Path(trace_dir)
    if not trace_root.exists():
        raise FileNotFoundError(f"trace_dir does not exist: {trace_dir}")
    if not trace_root.is_dir():
        raise NotADirectoryError(f"trace_dir is not a directory: {trace_dir}")

    failures: List[FailureCase] = []

    for path in sorted(trace_root.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        req = data.get("request", {})
        raw = data.get("raw_response", {})
        validation = data.get("validation", {})
        tool_map = _tool_schema_map(data)
        schema_hash = tool_schema_hash(tool_map)
        explicit_literals = _explicit_context_literals(data)
        tool_state = extract_tool_state(data)
        if not explicit_literals and tool_state.explicit_literals:
            explicit_literals = list(tool_state.explicit_literals)
        action_candidates = [candidate.to_dict() for candidate in generate_action_candidates(tool_state, tool_map)]
        candidate_recommended_tools = [
            tool
            for candidate in action_candidates
            for tool in candidate.get("recommended_tools", [])
            if isinstance(tool, str) and tool.strip()
        ]
        seen_failure_keys: set[tuple[str, int, str, str, str | None]] = set()
        inferred_no_tool_call_kind: str | None = None
        inferred_no_tool_subfamily: str | None = None
        inferred_no_tool_classification: FailureClassification | None = None
        inferred_no_tool_predicates: list[str] = []
        redundant_clarification_detected = False
        raw_implies_text_tool_call = False
        recommended_tools = list(dict.fromkeys(candidate_recommended_tools)) or (
            [] if tool_state.stop_allowed else _rank_recommended_tools(data, tool_map, explicit_literals)
        )

        def record_failure(case: FailureCase) -> None:
            # Validation issues can mirror failures already inferable from the raw response.
            # Deduplicate on the semantic failure identity and keep the first record.
            key = (case.trace_id, case.turn_index, case.tool_name, case.error_type, case.field_name)
            if key in seen_failure_keys:
                return
            seen_failure_keys.add(key)
            updates: dict[str, Any] = {}
            if not case.tool_schema_hash or case.tool_schema_hash == "*":
                updates["tool_schema_hash"] = schema_hash
            if not case.stage or not case.failure_type or not case.failure_label:
                classification = classify_error_type(
                    case.error_type,
                    request_predicates=case.request_predicates,
                    has_prior_tool_output=_has_prior_tool_outputs(data),
                )
                updates.update(
                    {
                        "stage": case.stage or classification.stage.value,
                        "failure_type": case.failure_type or classification.failure_type.value,
                        "failure_label": case.failure_label or classification.label,
                        "predicate_evidence": case.predicate_evidence or classification.predicate_evidence,
                    }
                )
            if not case.recommended_tools and recommended_tools:
                updates["recommended_tools"] = recommended_tools
            if not case.action_candidates and action_candidates:
                updates["action_candidates"] = action_candidates
            if updates:
                case = case.model_copy(update=updates)
            failures.append(case)

        for choice in raw.get("choices", []):
            msg = choice.get("message", {})
            tool_calls = msg.get("tool_calls", [])
            parsed = parse_text_tool_calls(msg.get("content", ""))
            usage = raw.get("usage", {})
            completion_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
            empty_completion = (
                msg.get("content") is None
                and not tool_calls
                and completion_tokens == 0
                and choice.get("finish_reason") in {None, "stop"}
            )
            if parsed:
                raw_implies_text_tool_call = True
            if tool_map and not tool_calls:
                if parsed:
                    for call in parsed:
                        fn = call.get("function", {})
                        if isinstance(fn.get("arguments"), dict):
                            fn["arguments"] = json.dumps(fn["arguments"], ensure_ascii=False)
                    tool_calls = parsed

            if not tool_calls and not parsed:
                inferred_no_tool_call_kind = (
                    "empty_completion"
                    if empty_completion
                    else classify_no_tool_call_content(msg.get("content", ""), tool_map)
                )
                if inferred_no_tool_call_kind == "clarification_request":
                    redundant_clarification_detected = _is_redundant_clarification_request(
                        data,
                        msg.get("content", ""),
                    )
                (
                    inferred_no_tool_subfamily,
                    inferred_no_tool_predicates,
                    inferred_no_tool_classification,
                ) = _classify_no_tool_subfamily(
                    data,
                    inferred_no_tool_call_kind,
                    tool_map,
                    explicit_literals=explicit_literals,
                    redundant_clarification_detected=redundant_clarification_detected,
                )
                if action_candidates and inferred_no_tool_subfamily in {"empty_tool_call", "empty_completion"}:
                    inferred_no_tool_subfamily = "actionable_no_tool_decision"
                    inferred_no_tool_predicates = ["tools_available"]
                    if tool_state.explicit_literals:
                        inferred_no_tool_predicates.append("prior_explicit_literals_present")
                    if tool_state.prior_tool_outputs:
                        inferred_no_tool_predicates.append("prior_tool_outputs_present")
                    inferred_no_tool_classification = classify_error_type(
                        "actionable_no_tool_decision",
                        request_predicates=inferred_no_tool_predicates,
                        has_prior_tool_output=bool(tool_state.prior_tool_outputs),
                    )

            if tool_map and not tool_calls:
                if inferred_no_tool_subfamily:
                    record_failure(
                        FailureCase(
                            trace_id=path.stem,
                            turn_index=0,
                            tool_name="__none__",
                            error_type=inferred_no_tool_subfamily,
                            stage=(
                                inferred_no_tool_classification.stage.value
                                if inferred_no_tool_classification
                                else None
                            ),
                            failure_type=(
                                inferred_no_tool_classification.failure_type.value
                                if inferred_no_tool_classification
                                else None
                            ),
                            failure_label=(
                                inferred_no_tool_classification.label
                                if inferred_no_tool_classification
                                else None
                            ),
                            request_predicates=inferred_no_tool_predicates,
                            request_literals=(
                                list(explicit_literals or tool_state.explicit_literals)
                                if inferred_no_tool_subfamily == "actionable_no_tool_decision"
                                else []
                            ),
                            predicate_evidence=(
                                inferred_no_tool_classification.predicate_evidence
                                if inferred_no_tool_classification
                                else {}
                            ),
                            recommended_tools=recommended_tools,
                            action_candidates=action_candidates,
                        )
                    )

            for turn_idx, tool_call in enumerate(tool_calls):
                name = tool_call.get("function", {}).get("name")
                if not name:
                    record_failure(
                        FailureCase(
                            trace_id=path.stem,
                            turn_index=turn_idx,
                            tool_name="__none__",
                            error_type="wrong_tool_name",
                        )
                    )
                    continue

                if name not in tool_map:
                    record_failure(
                        FailureCase(
                            trace_id=path.stem,
                            turn_index=turn_idx,
                            tool_name=name,
                            error_type="wrong_tool_name",
                        )
                    )
                    continue

                args_text = tool_call.get("function", {}).get("arguments", "{}")
                schema = tool_map[name]

                try:
                    args = parse_loose_json(args_text) if isinstance(args_text, str) else args_text
                except Exception:
                    record_failure(
                        FailureCase(
                            trace_id=path.stem,
                            turn_index=turn_idx,
                            tool_name=name,
                            error_type="invalid_json_args",
                        )
                    )
                    continue

                if not isinstance(args, dict):
                    record_failure(
                        FailureCase(
                            trace_id=path.stem,
                            turn_index=turn_idx,
                            tool_name=name,
                            error_type="non_object_args",
                        )
                    )
                    continue

                props = schema.get("properties", {})
                required = set(schema.get("required", []))

                for field in required:
                    if field not in args:
                        record_failure(
                            FailureCase(
                                trace_id=path.stem,
                                turn_index=turn_idx,
                                tool_name=name,
                                error_type="missing_required",
                                field_name=field,
                                expected_type=props.get(field, {}).get("type"),
                            )
                        )

                for field, value in args.items():
                    if field not in props:
                        record_failure(
                            FailureCase(
                                trace_id=path.stem,
                                turn_index=turn_idx,
                                tool_name=name,
                                error_type="unknown_field",
                                field_name=field,
                                observed_value=value,
                            )
                        )
                        continue

                    expected = props.get(field, {}).get("type")
                    if expected and not _python_matches_json_type(value, expected):
                        record_failure(
                            FailureCase(
                                trace_id=path.stem,
                                turn_index=turn_idx,
                                tool_name=name,
                                error_type="type_mismatch",
                                field_name=field,
                                expected_type=expected,
                                observed_value=value,
                            )
                        )

        for issue in validation.get("issues", []):
            issue_kind = issue.get("kind", "validation_issue")
            if issue_kind == "clarification_request":
                if redundant_clarification_detected:
                    record_failure(
                        FailureCase(
                            trace_id=path.stem,
                            turn_index=0,
                            tool_name=issue.get("tool_name") or "__none__",
                            error_type="redundant_clarification_request",
                            field_name=issue.get("field"),
                            category="verification_hook",
                        )
                    )
                continue
            if issue_kind in {"empty_tool_call", "empty_completion"}:
                if raw_implies_text_tool_call:
                    continue
                if inferred_no_tool_subfamily not in {None, "empty_tool_call", "empty_completion", "actionable_no_tool_decision"}:
                    continue
            record_failure(
                FailureCase(
                    trace_id=path.stem,
                    turn_index=0,
                    tool_name=issue.get("tool_name") or "__none__",
                    error_type=(
                        inferred_no_tool_subfamily
                        if issue_kind in {"empty_tool_call", "empty_completion"} and inferred_no_tool_subfamily
                        else issue_kind
                    ),
                    field_name=issue.get("field"),
                    category="verification_hook",
                    request_predicates=(
                        inferred_no_tool_predicates
                        if issue_kind in {"empty_tool_call", "empty_completion"} and inferred_no_tool_predicates
                        else []
                    ),
                    request_literals=(
                        list(explicit_literals)
                        if issue_kind in {"empty_tool_call", "empty_completion"}
                        and inferred_no_tool_subfamily == "actionable_no_tool_decision"
                        else []
                    ),
                    predicate_evidence=(
                        inferred_no_tool_classification.predicate_evidence
                        if issue_kind in {"empty_tool_call", "empty_completion"} and inferred_no_tool_classification
                        else {}
                    ),
                    recommended_tools=recommended_tools if tool_map else [],
                )
            )

    return failures
