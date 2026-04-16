from __future__ import annotations

import ast
import json
import re
from typing import Any, Dict, List

from grc.utils.jsonfix import parse_loose_json, strip_code_fence


_CALL_BLOCK_RE = re.compile(r"\[(.*)\]", re.DOTALL)
_CLARIFICATION_REQUEST_RE = re.compile(
    r"("
    r"could you (please )?(provide|tell me|specify)"
    r"|please (provide|tell me|specify)"
    r"|i still need"
    r"|i need to know"
    r"|i need (a bit more information|the|your)"
    r"|to proceed,? i require"
    r"|i require the following information"
    r"|you (haven't|have not) provided"
    r"|missing from your request"
    r"|once i have that information"
    r")",
    re.IGNORECASE,
)
_GENERIC_CLARIFICATION_PARAM_RE = re.compile(
    r"(information|details|parameter|parameters|field|fields|value|values)",
    re.IGNORECASE,
)
_UNSUPPORTED_REQUEST_RE = re.compile(
    r"("
    r"there is no function available"
    r"|don't have a specific function available"
    r"|do not have a specific function available"
    r"|can't directly"
    r"|cannot directly"
    r"|my tools are focused on"
    r"|outside the scope of the provided functions"
    r"|none of the functions can be used"
    r")",
    re.IGNORECASE,
)
_HALLUCINATED_COMPLETION_RE = re.compile(
    r"("
    r"i('ve| have) already initiated"
    r"|i('ve| have) already .*?(checked|started|called|initiated)"
    r"|once i have the results"
    r"|once i have the result"
    r"|i('ve| have) noted that"
    r")",
    re.IGNORECASE,
)
_REQUESTED_SLOT_RE = re.compile(
    r"(?:provide|tell me|specify|need to know|require)(?:\s+(?:the|your|a|an|specific))?\s+([a-z0-9][a-z0-9\s'_-]{1,100})",
    re.IGNORECASE,
)
_NON_WORD_SEP_RE = re.compile(r"[_/\\-]+")
_WHITESPACE_RE = re.compile(r"\s+")


def _split_top_level(text: str, sep: str = ",") -> List[str]:
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    in_str = False
    quote = ""
    escaped = False
    for ch in text:
        if in_str:
            current.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                in_str = False
            continue
        if ch in ("'", '"'):
            in_str = True
            quote = ch
            current.append(ch)
            continue
        if ch in "([{":
            depth += 1
            current.append(ch)
            continue
        if ch in ")]}":
            depth = max(0, depth - 1)
            current.append(ch)
            continue
        if ch == sep and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_value(raw: str) -> Any:
    raw = raw.strip()
    if not raw:
        return ""
    try:
        return ast.literal_eval(raw)
    except Exception:
        return raw.strip("'\"")


def _build_text_tool_call(tool_name: str, arguments: Any, index: int) -> Dict[str, Any]:
    return {
        "id": f"textcall_{index}",
        "type": "function",
        "function": {"name": tool_name, "arguments": arguments},
    }


def _parse_bracket_tool_calls(content: str) -> List[Dict[str, Any]]:
    match = _CALL_BLOCK_RE.search(content.strip())
    if not match:
        return []
    inner = match.group(1).strip()
    if not inner:
        return []

    calls: List[Dict[str, Any]] = []
    for call_expr in _split_top_level(inner, sep=","):
        call_expr = call_expr.strip()
        if "(" not in call_expr or not call_expr.endswith(")"):
            continue
        name, args_part = call_expr.split("(", 1)
        tool_name = name.strip()
        args_part = args_part[:-1].strip()
        if not tool_name:
            continue

        args_obj: Dict[str, Any] = {}
        if args_part:
            for arg_expr in _split_top_level(args_part, sep=","):
                if "=" not in arg_expr:
                    continue
                key, value = arg_expr.split("=", 1)
                key = key.strip()
                if not key:
                    continue
                args_obj[key] = _parse_value(value)

        calls.append(_build_text_tool_call(tool_name, args_obj, len(calls)))
    return calls


def _json_action_to_tool_calls(payload: Any) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    items = payload if isinstance(payload, list) else [payload]

    for item in items:
        if not isinstance(item, dict):
            continue
        tool_name = item.get("action")
        if not isinstance(tool_name, str) or not tool_name.strip():
            continue
        arguments = item.get("action_input", {})
        calls.append(_build_text_tool_call(tool_name.strip(), arguments, len(calls)))

    return calls


def _parse_json_action_tool_calls(content: str) -> List[Dict[str, Any]]:
    text = strip_code_fence(content)
    if not text or '"action"' not in text:
        return []

    decoder = json.JSONDecoder()
    cursor = text.lstrip()
    parsed_values: List[Any] = []

    while cursor:
        try:
            value, offset = decoder.raw_decode(cursor)
        except json.JSONDecodeError:
            parsed_values = []
            break
        parsed_values.append(value)
        cursor = cursor[offset:].lstrip()

    if parsed_values:
        calls: List[Dict[str, Any]] = []
        for value in parsed_values:
            calls.extend(_json_action_to_tool_calls(value))
        if calls:
            return calls

    try:
        payload = parse_loose_json(text)
    except Exception:
        return []

    return _json_action_to_tool_calls(payload)


def parse_text_tool_calls(content: str) -> List[Dict[str, Any]]:
    if not isinstance(content, str):
        return []

    bracket_calls = _parse_bracket_tool_calls(content)
    if bracket_calls:
        return bracket_calls

    return _parse_json_action_tool_calls(content)


def looks_like_terminal_natural_language(content: str) -> bool:
    if not isinstance(content, str):
        return False
    lowered = content.strip().lower()
    if not lowered:
        return False
    terminal_markers = (
        "i'm done",
        "i am done",
        "task is complete",
        "completed",
        "no further functions",
        "no more functions",
        "nothing else to do",
    )
    return any(marker in lowered for marker in terminal_markers)


def looks_like_malformed_output(content: str) -> bool:
    if not isinstance(content, str):
        return False
    stripped = content.strip()
    if not stripped:
        return False
    if stripped in {"[]", "{}"}:
        return False
    return len(stripped) <= 3 and not any(ch.isalnum() for ch in stripped)


def _normalize_hint_text(text: str) -> str:
    lowered = _NON_WORD_SEP_RE.sub(" ", text.strip().lower())
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return _WHITESPACE_RE.sub(" ", lowered).strip()


def _schema_hint_phrases(tool_schema_map: Dict[str, Dict[str, Any]] | None) -> set[str]:
    if not isinstance(tool_schema_map, dict):
        return set()

    hints: set[str] = set()
    for schema in tool_schema_map.values():
        if not isinstance(schema, dict):
            continue
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            continue
        for field_name, spec in properties.items():
            if isinstance(field_name, str):
                normalized_field = _normalize_hint_text(field_name)
                if normalized_field:
                    hints.add(normalized_field)
            if isinstance(spec, dict):
                description = spec.get("description")
                if isinstance(description, str):
                    normalized_description = _normalize_hint_text(description)
                    if normalized_description:
                        hints.add(normalized_description)
    return hints


def _content_mentions_schema_hint(content: str, tool_schema_map: Dict[str, Dict[str, Any]] | None) -> bool:
    normalized_content = _normalize_hint_text(content)
    if not normalized_content:
        return False

    content_tokens = set(normalized_content.split())
    hints = _schema_hint_phrases(tool_schema_map)
    if not hints:
        return False

    for hint in hints:
        if len(hint) < 3:
            continue
        if hint in normalized_content:
            return True
        hint_tokens = hint.split()
        if 1 <= len(hint_tokens) <= 4 and all(token in content_tokens for token in hint_tokens):
            return True
    return False


def _requested_slot_phrase(content: str) -> str:
    if not isinstance(content, str):
        return ""
    match = _REQUESTED_SLOT_RE.search(content.strip().lower())
    if not match:
        return ""
    phrase = match.group(1)
    for delimiter in (
        " before ",
        " once ",
        " so ",
        " to proceed",
        " to move",
        " to continue",
        " to complete",
        " to display",
        " to look",
        " to calculate",
        " you'd ",
        " you would ",
        ".",
        "?",
        "!",
        ",",
    ):
        if delimiter in phrase:
            phrase = phrase.split(delimiter, 1)[0]
    return _normalize_hint_text(phrase)


def looks_like_clarification_request(content: str, tool_schema_map: Dict[str, Dict[str, Any]] | None = None) -> bool:
    if not isinstance(content, str):
        return False
    lowered = content.strip().lower()
    if not lowered:
        return False
    if not _CLARIFICATION_REQUEST_RE.search(lowered):
        return False
    has_schema_hints = bool(_schema_hint_phrases(tool_schema_map))
    if _content_mentions_schema_hint(content, tool_schema_map):
        return True
    if has_schema_hints:
        return False
    if _requested_slot_phrase(content):
        return True
    return bool(_GENERIC_CLARIFICATION_PARAM_RE.search(lowered))


def looks_like_unsupported_request(content: str) -> bool:
    if not isinstance(content, str):
        return False
    lowered = content.strip().lower()
    if not lowered:
        return False
    return bool(_UNSUPPORTED_REQUEST_RE.search(lowered))


def looks_like_hallucinated_completion(content: str) -> bool:
    if not isinstance(content, str):
        return False
    lowered = content.strip().lower()
    if not lowered:
        return False
    return bool(_HALLUCINATED_COMPLETION_RE.search(lowered))


def classify_no_tool_call_content(content: str, tool_schema_map: Dict[str, Dict[str, Any]] | None = None) -> str:
    if looks_like_terminal_natural_language(content):
        return "natural_language_termination"
    if looks_like_malformed_output(content):
        return "malformed_output"
    if looks_like_hallucinated_completion(content):
        return "hallucinated_completion"
    if looks_like_unsupported_request(content):
        return "unsupported_request"
    if looks_like_clarification_request(content, tool_schema_map=tool_schema_map):
        return "clarification_request"
    return "empty_tool_call"
