from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Tuple

from grc.types import ToolSanitizerSpec
from grc.utils.jsonfix import parse_loose_json


JSON_SCHEMA_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _coerce_scalar(value: Any, expected_type: str) -> Any:
    if expected_type == "string":
        return str(value)
    if expected_type == "integer":
        if isinstance(value, bool):
            return int(value)
        return int(float(value))
    if expected_type == "number":
        return float(value)
    if expected_type == "boolean":
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return bool(value)
    return value


def _schema_field_type(tool_schema: Dict[str, Any], field: str) -> str | None:
    props = tool_schema.get("properties", {}) if isinstance(tool_schema, dict) else {}
    spec = props.get(field, {})
    return spec.get("type")


def sanitize_tool_call(
    tool_call: Dict[str, Any],
    tool_schema: Dict[str, Any],
    rule_spec: ToolSanitizerSpec | None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    repaired = copy.deepcopy(tool_call)
    repairs: List[Dict[str, Any]] = []

    fn = repaired.get("function", {})
    arg_text = fn.get("arguments", "{}")

    args = parse_loose_json(arg_text) if isinstance(arg_text, str) else arg_text
    if not isinstance(args, dict):
        raise ValueError("tool arguments must be a JSON object")

    original_args = copy.deepcopy(args)

    properties = tool_schema.get("properties", {}) if isinstance(tool_schema, dict) else {}
    required = set(tool_schema.get("required", []) if isinstance(tool_schema, dict) else [])

    fields_from_rule = rule_spec.fields if rule_spec else {}

    if rule_spec and rule_spec.strip_unknown_keys:
        unknown_keys = [key for key in list(args.keys()) if key not in properties and key not in fields_from_rule]
        for key in unknown_keys:
            args.pop(key, None)
            repairs.append({"kind": "drop_unknown_key", "field": key})

    for field, value in list(args.items()):
        expected_type = _schema_field_type(tool_schema, field)
        if not expected_type and field in fields_from_rule:
            expected_type = fields_from_rule[field].type

        if expected_type and rule_spec and rule_spec.coerce_types:
            py_type = JSON_SCHEMA_TYPE_MAP.get(expected_type)
            if py_type and not isinstance(value, py_type):
                try:
                    new_value = _coerce_scalar(value, expected_type)
                    args[field] = new_value
                    repairs.append(
                        {
                            "kind": "coerce_type",
                            "field": field,
                            "from": type(value).__name__,
                            "to": expected_type,
                        }
                    )
                except Exception:
                    pass

    if rule_spec and rule_spec.fill_defaults:
        for field, spec in fields_from_rule.items():
            if field not in args and spec.default is not None:
                args[field] = spec.default
                repairs.append({"kind": "fill_default", "field": field, "value": spec.default})

    for field, spec in fields_from_rule.items():
        if spec.required:
            required.add(field)

    missing = [field for field in required if field not in args]
    for field in missing:
        repairs.append({"kind": "missing_required", "field": field})

    fn["arguments"] = json.dumps(args, ensure_ascii=False)
    repaired["function"] = fn

    if args != original_args:
        repairs.append({"kind": "arguments_changed"})

    return repaired, repairs

