from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

from grc.types import FailureCase
from grc.utils.jsonfix import parse_loose_json


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


def mine_failures(trace_dir: str) -> List[FailureCase]:
    failures: List[FailureCase] = []

    for path in sorted(Path(trace_dir).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        req = data.get("request", {})
        raw = data.get("raw_response", {})
        validation = data.get("validation", {})
        tools = req.get("tools", [])
        tool_map = {
            tool["function"]["name"]: tool["function"].get("parameters", {})
            for tool in tools
            if tool.get("function", {}).get("name")
        }

        for choice in raw.get("choices", []):
            msg = choice.get("message", {})
            tool_calls = msg.get("tool_calls", [])

            if req.get("tools") and not tool_calls:
                failures.append(
                    FailureCase(
                        trace_id=path.stem,
                        turn_index=0,
                        tool_name="__none__",
                        error_type="empty_tool_call",
                    )
                )

            for turn_idx, tool_call in enumerate(tool_calls):
                name = tool_call.get("function", {}).get("name")
                if not name:
                    failures.append(
                        FailureCase(
                            trace_id=path.stem,
                            turn_index=turn_idx,
                            tool_name="__none__",
                            error_type="wrong_tool_name",
                        )
                    )
                    continue

                if name not in tool_map:
                    failures.append(
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
                    failures.append(
                        FailureCase(
                            trace_id=path.stem,
                            turn_index=turn_idx,
                            tool_name=name,
                            error_type="invalid_json_args",
                        )
                    )
                    continue

                if not isinstance(args, dict):
                    failures.append(
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
                        failures.append(
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
                        failures.append(
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
                        failures.append(
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
            failures.append(
                FailureCase(
                    trace_id=path.stem,
                    turn_index=0,
                    tool_name=issue.get("tool_name") or "__none__",
                    error_type=issue.get("kind", "validation_issue"),
                    field_name=issue.get("field"),
                    category="verification_hook",
                )
            )

    return failures
