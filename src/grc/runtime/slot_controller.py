from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple

from grc.utils.jsonfix import parse_loose_json


ABHE_RUNTIME_SLOT_CONTROLLER_PATCH = "abhe_v0_runtime_slot_controller_v2:enabled"


@dataclass(frozen=True)
class RuntimeSlotPatch:
    field: str
    source_type: str


def _schema_required(schema: Dict[str, Any]) -> List[str]:
    required = schema.get("required") if isinstance(schema.get("required"), list) else []
    return [str(item) for item in required if isinstance(item, str) and item.strip()]


def _schema_types(schema: Dict[str, Any]) -> Dict[str, str]:
    props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    out: Dict[str, str] = {}
    for key, meta in props.items():
        if isinstance(key, str) and isinstance(meta, dict):
            out[key] = str(meta.get("type") or "unknown")
    return out


def _type_compatible(value: Any, expected_type: str | None) -> bool:
    if value is None:
        return False
    if not expected_type or expected_type == "unknown":
        return True
    if expected_type == "string":
        return isinstance(value, str) and bool(value.strip())
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    return True


def _parse_args(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = parse_loose_json(value)
        except Exception:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _parse_jsonlike(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return None
    try:
        return json.loads(stripped)
    except Exception:
        try:
            return parse_loose_json(stripped)
        except Exception:
            return None


def _walk_key_values(value: Any, slot: str) -> Iterable[Any]:
    stack = [value]
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            for key, child in item.items():
                if key == slot:
                    yield child
                if isinstance(child, (dict, list)):
                    stack.append(child)
        elif isinstance(item, list):
            stack.extend(child for child in item if isinstance(child, (dict, list)))


def _candidate_sources_from_request(request_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    messages = request_json.get("messages") if isinstance(request_json.get("messages"), list) else []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role == "assistant":
            for call in message.get("tool_calls") or []:
                if not isinstance(call, dict):
                    continue
                fn = call.get("function") if isinstance(call.get("function"), dict) else {}
                args = _parse_args(fn.get("arguments"))
                if args:
                    sources.append({"source_type": "prior_assistant_tool_call", "values": args})
        elif role == "tool":
            parsed = _parse_jsonlike(message.get("content"))
            if parsed is not None:
                sources.append({"source_type": "prior_tool_observation", "values": parsed})
    return sources


def _unique_compatible_source(slot: str, expected_type: str | None, sources: List[Dict[str, Any]]) -> Tuple[Any, str] | None:
    matches: List[Tuple[Any, str]] = []
    seen: set[str] = set()
    for source in sources:
        source_type = str(source.get("source_type") or "unknown")
        values = source.get("values")
        for value in _walk_key_values(values, slot):
            if not _type_compatible(value, expected_type):
                continue
            marker = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            if marker in seen:
                continue
            seen.add(marker)
            matches.append((value, source_type))
    if len(matches) == 1:
        return matches[0]
    return None


def runtime_slot_controller_v2_apply(
    *,
    request_json: Dict[str, Any],
    tool_name: str,
    schema: Dict[str, Any],
    args: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    required = _schema_required(schema)
    types = _schema_types(schema)
    missing = [slot for slot in required if slot not in args or not _type_compatible(args.get(slot), types.get(slot))]
    telemetry: Dict[str, Any] = {
        "mechanism_id": "runtime_slot_controller_v2",
        "tool_name_present": bool(tool_name),
        "required_arg_count": len(required),
        "missing_required_arg_count_before": len(missing),
        "bound_slot_count": 0,
        "ambiguous_or_unresolved_count": 0,
        "valid_tool_call_allowed": not missing,
    }
    if not missing:
        return args, [], telemetry

    sources = _candidate_sources_from_request(request_json)
    patched = dict(args)
    repairs: List[Dict[str, Any]] = []
    unresolved = 0
    for slot in missing:
        match = _unique_compatible_source(slot, types.get(slot), sources)
        if match is None:
            unresolved += 1
            continue
        value, source_type = match
        patched[slot] = value
        repairs.append(
            {
                "kind": "abhe_runtime_slot_controller_v2_bind_required_slot",
                "tool_name": tool_name,
                "field": slot,
                "source_type": source_type,
                "raw_value_committed": False,
            }
        )
    telemetry["bound_slot_count"] = len(repairs)
    telemetry["ambiguous_or_unresolved_count"] = unresolved
    telemetry["missing_required_arg_count_after"] = unresolved
    telemetry["valid_tool_call_allowed"] = unresolved == 0
    return patched, repairs, telemetry


def runtime_slot_controller_enabled(request_patches: List[str] | None) -> bool:
    return ABHE_RUNTIME_SLOT_CONTROLLER_PATCH in set(request_patches or [])
