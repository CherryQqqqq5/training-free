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
_CLARIFICATION_PARAM_RE = re.compile(
    r"("
    r"stock symbol"
    r"|company name"
    r"|company"
    r"|name or symbol"
    r"|symbol of the stock"
    r"|ticker"
    r"|zip code"
    r"|zip codes"
    r"|full address"
    r"|full addresses"
    r"|city"
    r"|city and state"
    r"|state"
    r"|current location"
    r"|starting point"
    r"|sector"
    r"|location"
    r"|target currency"
    r"|currency"
    r"|file name"
    r"|name of the file"
    r"|personal details"
    r"|traveler information"
    r"|first name"
    r"|last name"
    r"|date of birth"
    r"|passport number"
    r"|address"
    r"|information"
    r"|details"
    r"|parameter"
    r")",
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


def looks_like_clarification_request(content: str) -> bool:
    if not isinstance(content, str):
        return False
    lowered = content.strip().lower()
    if not lowered:
        return False
    if not _CLARIFICATION_REQUEST_RE.search(lowered):
        return False
    return bool(_CLARIFICATION_PARAM_RE.search(lowered))


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


def classify_no_tool_call_content(content: str) -> str:
    if looks_like_terminal_natural_language(content):
        return "natural_language_termination"
    if looks_like_malformed_output(content):
        return "malformed_output"
    if looks_like_hallucinated_completion(content):
        return "hallucinated_completion"
    if looks_like_unsupported_request(content):
        return "unsupported_request"
    if looks_like_clarification_request(content):
        return "clarification_request"
    return "empty_tool_call"
