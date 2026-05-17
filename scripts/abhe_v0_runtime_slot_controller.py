#!/usr/bin/env python3
"""ABHE-v0 compact runtime slot controller primitives.

These helpers are intentionally pure and fixture-driven. They do not call a
provider, BFCL, or scorer, and they do not persist raw benchmark material.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


@dataclass(frozen=True)
class SlotStatus:
    name: str
    status: str
    source: str | None = None
    compatible: bool = False


def _function_schema(tool: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    fn = tool.get("function") if isinstance(tool.get("function"), dict) else tool
    name = str(fn.get("name") or tool.get("name") or "")
    params = fn.get("parameters") if isinstance(fn.get("parameters"), dict) else fn
    return name, params if isinstance(params, dict) else {}


def required_arg_schema_reader_v0(tool: Dict[str, Any]) -> Dict[str, Any]:
    name, schema = _function_schema(tool)
    properties = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
    required = [str(item) for item in (schema.get("required") or []) if isinstance(item, str)]
    return {
        "mechanism_id": "required_arg_schema_reader_v0",
        "tool_name_hashable": bool(name),
        "required_arg_count": len(required),
        "required_args": sorted(required),
        "property_type_by_arg": {
            key: str(value.get("type") or "unknown")
            for key, value in properties.items()
            if isinstance(value, dict)
        },
    }


def _type_compatible(value: Any, expected_type: str | None) -> bool:
    if not expected_type or expected_type == "unknown":
        return value is not None
    if expected_type == "string":
        return isinstance(value, str) and value != ""
    if expected_type in {"integer", "number"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    return value is not None


def valid_tool_call_guard_v0(tool_call: Dict[str, Any], schema_read: Dict[str, Any]) -> Dict[str, Any]:
    args = tool_call.get("arguments") if isinstance(tool_call.get("arguments"), dict) else {}
    required = list(schema_read.get("required_args") or [])
    types = schema_read.get("property_type_by_arg") if isinstance(schema_read.get("property_type_by_arg"), dict) else {}
    missing = [slot for slot in required if slot not in args]
    incompatible = [slot for slot in required if slot in args and not _type_compatible(args.get(slot), types.get(slot))]
    valid = not missing and not incompatible
    return {
        "mechanism_id": "valid_tool_call_guard_v0",
        "tool_call_valid": valid,
        "missing_required_args": missing,
        "incompatible_required_args": incompatible,
        "allow_without_rewrite": valid,
        "would_block_valid_tool_call": False,
    }


def _lookup_source(slot: str, sources: List[Dict[str, Any]], expected_type: str | None) -> SlotStatus:
    matches: List[Tuple[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        values = source.get("values") if isinstance(source.get("values"), dict) else {}
        if slot in values and _type_compatible(values.get(slot), expected_type):
            matches.append((str(source.get("source_type") or "unknown"), values.get(slot)))
    if len(matches) == 1:
        return SlotStatus(slot, "known", source=matches[0][0], compatible=True)
    if len(matches) > 1:
        return SlotStatus(slot, "ambiguous", source="multiple", compatible=False)
    return SlotStatus(slot, "missing", source=None, compatible=False)


def prior_tool_observation_slot_binder_v0(schema_read: Dict[str, Any], tool_call: Dict[str, Any], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    args = tool_call.get("arguments") if isinstance(tool_call.get("arguments"), dict) else {}
    types = schema_read.get("property_type_by_arg") if isinstance(schema_read.get("property_type_by_arg"), dict) else {}
    bound: Dict[str, str] = {}
    ambiguous: List[str] = []
    missing_after_bind: List[str] = []
    for slot in schema_read.get("required_args") or []:
        if slot in args and _type_compatible(args.get(slot), types.get(slot)):
            continue
        status = _lookup_source(str(slot), sources, types.get(slot))
        if status.status == "known" and status.compatible:
            bound[str(slot)] = str(status.source)
        elif status.status == "ambiguous":
            ambiguous.append(str(slot))
        else:
            missing_after_bind.append(str(slot))
    return {
        "mechanism_id": "prior_tool_observation_slot_binder_v0",
        "bound_slot_sources": bound,
        "ambiguous_slots": sorted(ambiguous),
        "missing_after_bind": sorted(missing_after_bind),
        "bindable_count": len(bound),
        "entity_ambiguity_detected": bool(ambiguous),
    }


def prerequisite_lookup_planner_v0(missing_slots: List[str], available_tools: List[Dict[str, Any]], recoverability_map: Dict[str, str]) -> Dict[str, Any]:
    available_names = {str((_function_schema(tool)[0] or "")) for tool in available_tools}
    planned: Dict[str, str] = {}
    unrecoverable: List[str] = []
    for slot in missing_slots:
        tool_name = recoverability_map.get(slot)
        if tool_name and tool_name in available_names:
            planned[slot] = tool_name
        else:
            unrecoverable.append(slot)
    return {
        "mechanism_id": "prerequisite_lookup_planner_v0",
        "planned_lookup_by_slot": planned,
        "lookup_needed_count": len(planned),
        "unrecoverable_slots": sorted(unrecoverable),
        "ask_or_insufficient_required": bool(unrecoverable),
    }


def runtime_slot_controller_v2(tool: Dict[str, Any], tool_call: Dict[str, Any], sources: List[Dict[str, Any]], available_tools: List[Dict[str, Any]], recoverability_map: Dict[str, str]) -> Dict[str, Any]:
    schema_read = required_arg_schema_reader_v0(tool)
    guard = valid_tool_call_guard_v0(tool_call, schema_read)
    if guard["tool_call_valid"]:
        return {
            "mechanism_id": "runtime_slot_controller_v2",
            "decision": "allow_valid_tool_call",
            "schema_reader": schema_read,
            "valid_tool_call_guard": guard,
            "slot_binder": None,
            "lookup_planner": None,
            "would_block_valid_tool_call": False,
        }
    binder = prior_tool_observation_slot_binder_v0(schema_read, tool_call, sources)
    remaining = list(binder["missing_after_bind"]) + list(binder["ambiguous_slots"])
    planner = prerequisite_lookup_planner_v0(remaining, available_tools, recoverability_map)
    if binder["entity_ambiguity_detected"]:
        decision = "ask_or_insufficient_due_ambiguity"
    elif planner["lookup_needed_count"]:
        decision = "call_prerequisite_lookup"
    elif binder["bindable_count"]:
        decision = "bind_recovered_slots_then_call"
    else:
        decision = "ask_or_insufficient"
    return {
        "mechanism_id": "runtime_slot_controller_v2",
        "decision": decision,
        "schema_reader": schema_read,
        "valid_tool_call_guard": guard,
        "slot_binder": binder,
        "lookup_planner": planner,
        "would_block_valid_tool_call": False,
    }
