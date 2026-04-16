from __future__ import annotations

from typing import Any


def normalize_schema_type(value: Any) -> Any:
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


def normalize_schema(schema: Any) -> Any:
    if isinstance(schema, dict):
        normalized = {key: normalize_schema(value) for key, value in schema.items()}
        if "type" in normalized:
            normalized["type"] = normalize_schema_type(normalized["type"])
        return normalized
    if isinstance(schema, list):
        return [normalize_schema(item) for item in schema]
    return schema


def tool_map_from_tools_payload(tools: Any) -> dict[str, dict[str, Any]]:
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
            tool_map[name] = normalize_schema(params) if isinstance(params, dict) else {}

    return tool_map


def normalize_tool_schema_snapshot(snapshot: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return {}

    normalized: dict[str, dict[str, Any]] = {}
    for name, schema in snapshot.items():
        if isinstance(name, str) and name and isinstance(schema, dict):
            normalized[name] = normalize_schema(schema)
    return normalized
