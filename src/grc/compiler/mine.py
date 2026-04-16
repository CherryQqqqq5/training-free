from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List

from grc.types import FailureCase
from grc.utils.jsonfix import parse_loose_json
from grc.utils.text_tool_calls import (
    classify_no_tool_call_content,
    parse_text_tool_calls,
)

_FUNCTION_LIST_MARKER_RE = re.compile(
    r"Here is a list of functions in json format that you can invoke\.\n(\[.*\])\s*$",
    re.DOTALL,
)


def _normalize_schema_type(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    lowered = value.strip().lower()
    aliases = {
        "dict": "object",
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
    }
    return aliases.get(lowered, lowered)


def _normalize_schema(schema: Any) -> Any:
    if isinstance(schema, dict):
        normalized = {key: _normalize_schema(value) for key, value in schema.items()}
        if "type" in normalized:
            normalized["type"] = _normalize_schema_type(normalized["type"])
        return normalized
    if isinstance(schema, list):
        return [_normalize_schema(item) for item in schema]
    return schema


def _tool_map_from_tools_payload(tools: Any) -> dict[str, dict[str, Any]]:
    tool_map: dict[str, dict[str, Any]] = {}
    if not isinstance(tools, list):
        return tool_map

    for tool in tools:
        if not isinstance(tool, dict):
            continue

        if "function" in tool and isinstance(tool.get("function"), dict):
            fn = tool["function"]
            name = fn.get("name")
            params = fn.get("parameters", {})
        else:
            name = tool.get("name")
            params = tool.get("parameters", {})

        if isinstance(name, str) and name:
            tool_map[name] = _normalize_schema(params) if isinstance(params, dict) else {}

    return tool_map


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

    return _tool_map_from_tools_payload(functions)


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
        _tool_map_from_tools_payload(req.get("tools") if isinstance(req, dict) else None),
        _tool_map_from_messages(req.get("messages") if isinstance(req, dict) else None),
        _tool_map_from_tools_payload(request_original.get("tools") if isinstance(request_original, dict) else None),
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


def _inferred_no_tool_call_kind(content: Any) -> str | None:
    if not isinstance(content, str):
        return None
    return classify_no_tool_call_content(content)


def mine_failures(trace_dir: str) -> List[FailureCase]:
    failures: List[FailureCase] = []

    for path in sorted(Path(trace_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        req = data.get("request", {})
        raw = data.get("raw_response", {})
        validation = data.get("validation", {})
        tool_map = _tool_schema_map(data)
        seen_failure_keys: set[tuple[str, int, str, str, str | None]] = set()
        inferred_no_tool_call_kind: str | None = None
        raw_implies_text_tool_call = False

        def record_failure(case: FailureCase) -> None:
            # Validation issues can mirror failures already inferable from the raw response.
            # Deduplicate on the semantic failure identity and keep the first record.
            key = (case.trace_id, case.turn_index, case.tool_name, case.error_type, case.field_name)
            if key in seen_failure_keys:
                return
            seen_failure_keys.add(key)
            failures.append(case)

        for choice in raw.get("choices", []):
            msg = choice.get("message", {})
            tool_calls = msg.get("tool_calls", [])
            parsed = parse_text_tool_calls(msg.get("content", ""))
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
                inferred_no_tool_call_kind = _inferred_no_tool_call_kind(msg.get("content", ""))

            if tool_map and not tool_calls:
                if inferred_no_tool_call_kind != "clarification_request":
                    record_failure(
                        FailureCase(
                            trace_id=path.stem,
                            turn_index=0,
                            tool_name="__none__",
                            error_type=inferred_no_tool_call_kind or "empty_tool_call",
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
                continue
            if issue_kind == "empty_tool_call":
                if raw_implies_text_tool_call:
                    continue
                if inferred_no_tool_call_kind not in {None, "empty_tool_call"}:
                    continue
            record_failure(
                FailureCase(
                    trace_id=path.stem,
                    turn_index=0,
                    tool_name=issue.get("tool_name") or "__none__",
                    error_type=issue_kind,
                    field_name=issue.get("field"),
                    category="verification_hook",
                )
            )

    return failures
