from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from grc.utils.text_tool_calls import parse_text_tool_calls
from grc.utils.tool_schema import tool_map_from_tools_payload


_TOOL_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_QUOTED_LITERAL_RE = re.compile(r"'([^'\n]{1,120})'|\"([^\"\n]{1,120})\"")


def _parse_balanced_call_at(content: str, start: int) -> str | None:
    depth = 0
    in_str = False
    quote = ""
    escaped = False
    seen_open = False
    for index in range(start, len(content)):
        ch = content[index]
        if in_str:
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
            continue
        if ch == "(":
            depth += 1
            seen_open = True
            continue
        if ch == ")":
            if depth == 0:
                return None
            depth -= 1
            if seen_open and depth == 0:
                return content[start : index + 1]
    return None


def _parse_embedded_tool_calls(content: str, candidate_tool_names: List[str]) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for tool_name in candidate_tool_names:
        pattern = re.compile(rf"\b{re.escape(tool_name)}\s*\(")
        for match in pattern.finditer(content):
            call_expr = _parse_balanced_call_at(content, match.start())
            if not call_expr:
                continue
            parsed = parse_text_tool_calls(call_expr)
            if parsed:
                calls.extend(parsed)
    return calls


def _parse_generic_embedded_tool_calls(content: str) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for match in _TOOL_NAME_RE.finditer(content):
        start = match.start()
        name = match.group(0)
        end = match.end()
        cursor = end
        while cursor < len(content) and content[cursor].isspace():
            cursor += 1
        if cursor >= len(content) or content[cursor] != "(":
            continue
        call_expr = _parse_balanced_call_at(content, start)
        if not call_expr:
            continue
        parsed = parse_text_tool_calls(call_expr)
        if parsed:
            calls.extend(parsed)
    return calls


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def _extract_labeled_value(content: str, field_name: str) -> str | None:
    labels = {field_name, field_name.replace("_", " ")}
    for label in labels:
        normalized = _normalize_label(label)
        if not normalized:
            continue
        patterns = [
            rf"\b{re.escape(normalized)}\b\s*(?:=|:|is|as)\s*'([^'\n]{{1,120}})'",
            rf'\b{re.escape(normalized)}\b\s*(?:=|:|is|as)\s*"([^"\n]{{1,120}})"',
            rf"\b{re.escape(normalized)}\b\s*(?:=|:|is|as)\s*([A-Za-z0-9_./:-]{{1,120}})",
        ]
        normalized_content = _normalize_label(content)
        raw_match = re.search(patterns[0], normalized_content)
        if raw_match:
            return raw_match.group(1)
        raw_match = re.search(patterns[1], normalized_content)
        if raw_match:
            return raw_match.group(1)
        raw_match = re.search(patterns[2], normalized_content)
        if raw_match:
            return raw_match.group(1)

    # Preserve original punctuation for quoted values if possible.
    for label in labels:
        patterns = [
            rf"\b{re.escape(label)}\b\s*(?:=|:|is|as)\s*'([^'\n]{{1,120}})'",
            rf'\b{re.escape(label)}\b\s*(?:=|:|is|as)\s*"([^"\n]{{1,120}})"',
            rf"\b{re.escape(label)}\b\s*(?:=|:|is|as)\s*([A-Za-z0-9_./:-]{{1,120}})",
        ]
        for pattern in patterns:
            match = re.search(pattern, content, flags=re.IGNORECASE)
            if match:
                return match.group(1)
    return None


def _convert_scalar(value: str, field_schema: Dict[str, Any]) -> Any:
    schema_type = field_schema.get("type")
    if schema_type == "integer":
        try:
            return int(value)
        except Exception:
            return value
    if schema_type == "number":
        try:
            return float(value)
        except Exception:
            return value
    if schema_type == "boolean":
        lowered = value.lower()
        if lowered in {"true", "yes"}:
            return True
        if lowered in {"false", "no"}:
            return False
    return value


def _tool_name_mentioned(content: str, tool_name: str) -> bool:
    normalized_tool = _normalize_label(tool_name)
    normalized_content = _normalize_label(content)
    return bool(normalized_tool and normalized_tool in normalized_content)


def _recover_from_tool_schema(content: str, tools_payload: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tool_map = tool_map_from_tools_payload(tools_payload)
    if not tool_map:
        return []

    tool_names = list(tool_map.keys())
    embedded = _parse_embedded_tool_calls(content, tool_names)
    if embedded:
        return embedded

    candidate_tool_names = [name for name in tool_names if _tool_name_mentioned(content, name)]
    if not candidate_tool_names and len(tool_names) == 1:
        candidate_tool_names = tool_names[:]
    if len(candidate_tool_names) != 1:
        return []

    tool_name = candidate_tool_names[0]
    schema = tool_map.get(tool_name, {})
    properties = schema.get("properties", {}) if isinstance(schema, dict) else {}
    required = schema.get("required", []) if isinstance(schema, dict) else []
    if not isinstance(properties, dict):
        return []
    if not isinstance(required, list):
        required = []

    arguments: Dict[str, Any] = {}
    for field_name, field_schema in properties.items():
        if not isinstance(field_name, str):
            continue
        if not isinstance(field_schema, dict):
            field_schema = {}
        value = _extract_labeled_value(content, field_name)
        if value is None:
            continue
        arguments[field_name] = _convert_scalar(value, field_schema)

    if required and not all(field in arguments for field in required):
        return []
    if not arguments:
        return []

    return [
        {
            "id": "nlcall_0",
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
    ]


def recover_high_confidence_tool_calls(content: str, tools_payload: List[Dict[str, Any]] | None = None) -> List[Dict[str, Any]]:
    if not isinstance(content, str):
        return []

    direct = parse_text_tool_calls(content)
    if direct:
        return direct

    stripped = content.strip()
    if not stripped:
        return []

    try:
        parsed = json.loads(stripped)
    except Exception:
        parsed = None
    if isinstance(parsed, (dict, list)):
        reparsed = parse_text_tool_calls(json.dumps(parsed, ensure_ascii=False))
        if reparsed:
            return reparsed

    generic_embedded = _parse_generic_embedded_tool_calls(stripped)
    if generic_embedded:
        return generic_embedded

    if tools_payload:
        return _recover_from_tool_schema(stripped, tools_payload)
    return []
