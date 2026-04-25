from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from grc.compiler.tool_state import ToolState, first_match_basename, is_strict_file_literal


@dataclass
class ActionCandidate:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    arg_bindings: dict[str, dict[str, Any]] = field(default_factory=dict)
    recommended_tools: list[str] = field(default_factory=list)
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    binding_source: str = ""
    postcondition: dict[str, Any] = field(default_factory=dict)
    trajectory_risk_score: int = 0
    trajectory_risk_flags: list[str] = field(default_factory=list)
    binding_type: str = "unknown"
    intervention_mode: str = "guidance"
    pending_goal_family: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "args": self.args,
            "arg_bindings": self.arg_bindings,
            "recommended_tools": self.recommended_tools or [self.tool],
            "reason": self.reason,
            "evidence": self.evidence,
            "binding_source": self.binding_source,
            "postcondition": self.postcondition,
            "trajectory_risk_score": self.trajectory_risk_score,
            "trajectory_risk_flags": self.trajectory_risk_flags,
            "binding_type": self.binding_type,
            "intervention_mode": self.intervention_mode,
            "pending_goal_family": self.pending_goal_family,
        }


def _has_tool(state: ToolState, tool_name: str) -> bool:
    return tool_name in state.tool_schemas


def _first_required_arg(schema: dict[str, Any], preferred: list[str]) -> str | None:
    required = list(schema.get("required") or [])
    properties = schema.get("properties") or {}
    for name in preferred:
        if name in required or name in properties:
            return name
    if required:
        return str(required[0])
    if properties:
        return str(next(iter(properties.keys())))
    return None


def _ordered_args(schema: dict[str, Any], preferred: list[str]) -> list[str]:
    required = [str(item) for item in (schema.get("required") or []) if isinstance(item, str)]
    properties = schema.get("properties") or {}
    ordered: list[str] = []
    for name in preferred:
        if name in required or name in properties:
            ordered.append(name)
    for name in required:
        if name not in ordered:
            ordered.append(name)
    for name in properties:
        if name not in ordered:
            ordered.append(str(name))
    return ordered


def _literal_for_tool(state: ToolState, tool_name: str) -> str | None:
    if not state.explicit_literals:
        return None
    lowered = state.latest_user_text.lower()
    if tool_name == "lookup_id":
        return state.explicit_literals[0]
    file_literals = [item for item in state.explicit_literals if is_strict_file_literal(item)]
    if tool_name in {"cat", "delete_file", "touch"} and file_literals:
        return file_literals[0]
    if tool_name == "mkdir":
        return state.explicit_literals[0]
    if "read" in lowered or "open" in lowered:
        return state.explicit_literals[0]
    return state.explicit_literals[0]


def _read_file_value(state: ToolState) -> tuple[str | None, str, dict[str, Any]]:
    match_value = first_match_basename(state)
    if match_value:
        return (
            match_value,
            "prior_tool_output.matches[0]|basename",
            {"last_tool": state.last_tool, "prior_output_keys": state.prior_output_keys},
        )
    file_literals = [item for item in state.explicit_literals if is_strict_file_literal(item)]
    if file_literals:
        return (
            file_literals[0],
            "explicit_literal",
            {"explicit_literals": state.explicit_literals, "intent": state.user_intent_family},
        )
    lowered = state.latest_user_text.lower()
    for output in state.prior_tool_outputs:
        entries = output.content.get("entries") if isinstance(output.content, dict) else None
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, str):
                continue
            basename = entry.rstrip("/").split("/")[-1]
            if not is_strict_file_literal(basename):
                continue
            stem = basename.rsplit(".", 1)[0].lower()
            if basename.lower() in lowered or stem in lowered:
                return (
                    basename,
                    "prior_tool_output.entries|basename",
                    {"last_tool": state.last_tool, "prior_output_keys": state.prior_output_keys},
                )
    return None, "", {}


def _move_copy_values(state: ToolState) -> tuple[str | None, str | None, str, dict[str, Any]]:
    file_literals = [item for item in state.explicit_literals if is_strict_file_literal(item)]
    if len(file_literals) >= 2:
        return (
            file_literals[0].rstrip("/").split("/")[-1],
            file_literals[1].rstrip("/").split("/")[-1],
            "explicit_literal_pair",
            {"explicit_literals": file_literals, "intent": state.user_intent_family},
        )
    match_value = first_match_basename(state)
    if match_value and file_literals:
        return (
            match_value,
            file_literals[0].rstrip("/").split("/")[-1],
            "prior_tool_output.matches[0]+explicit_literal",
            {"last_tool": state.last_tool, "prior_output_keys": state.prior_output_keys, "explicit_literals": file_literals},
        )
    return None, None, "", {}


def _looks_like_file(value: str | None) -> bool:
    return is_strict_file_literal(value)


def _looks_like_directory(value: str | None) -> bool:
    if not value:
        return False
    if value.endswith("/"):
        return True
    return not _looks_like_file(value)


def _binding_type(tool: str, value: str | None) -> str:
    if tool == "lookup_id":
        return "id"
    if tool in {"touch", "delete_file"}:
        return "file" if value else "unknown"
    if tool == "cat":
        return "file" if _looks_like_file(value) else "unknown"
    if tool == "mkdir":
        return "directory" if _looks_like_directory(value) else "unknown"
    if tool in {"grep", "find"}:
        return "content"
    if tool in {"cp", "mv", "move_file", "copy_file"}:
        return "path"
    return "unknown"


_POSTCONDITION_GOALS = {
    "file_content": "read_content",
    "file_exists": "create_file",
    "directory_exists": "create_directory",
    "matches": "search",
    "target_path_changed": "move_or_copy",
}


def _postcondition(tool: str, arg_name: str | None, *, binding_type: str) -> dict[str, Any]:
    target_arg = arg_name or ""
    if tool == "cat" and binding_type == "file":
        return {"kind": "file_content", "expected_state_key": "file_content", "target_arg": target_arg, "confidence": 0.8}
    if tool == "touch" and binding_type == "file":
        return {"kind": "file_exists", "expected_state_key": "current_directory_content", "target_arg": target_arg, "confidence": 0.75}
    if tool == "mkdir" and binding_type == "directory":
        return {"kind": "directory_exists", "expected_state_key": "current_directory_content", "target_arg": target_arg, "confidence": 0.75}
    if tool in {"grep", "find"}:
        return {"kind": "matches", "expected_state_key": "matches", "target_arg": target_arg, "confidence": 0.7}
    if tool in {"cp", "mv", "move_file", "copy_file"}:
        return {"kind": "target_path_changed", "expected_state_key": "current_directory_content", "target_arg": target_arg, "confidence": 0.7}
    return {}


def _postcondition_matches_goal(postcondition: dict[str, Any], pending_goal_family: str) -> bool:
    kind = str(postcondition.get("kind") or "")
    expected_goal = _POSTCONDITION_GOALS.get(kind)
    if not expected_goal:
        return False
    return expected_goal == pending_goal_family


def _candidate_risk(tool: str, *, source: str, postcondition: dict[str, Any], pending_goal_family: str) -> tuple[int, list[str]]:
    flags: list[str] = []
    score = 0
    if tool in {"cat", "touch", "mkdir"}:
        flags.append("trajectory_sensitive_tool")
        score += 2
    if not postcondition:
        flags.append("postcondition_missing")
        score += 8
    elif not _postcondition_matches_goal(postcondition, pending_goal_family):
        flags.append("pending_goal_postcondition_mismatch")
        score += 8
    if source == "prior_tool_output.cwd_or_listing":
        flags.append("weak_cwd_or_listing_binding")
        score += 5
    elif source.startswith("prior_tool_output"):
        score += 2
    return score, flags


def _intervention_mode(risk_score: int) -> str:
    if risk_score >= 8:
        return "record_only"
    if risk_score >= 5:
        return "weak_guidance"
    return "guidance"


def _candidate(
    tool: str,
    arg_name: str | None,
    value: str | None,
    *,
    reason: str,
    evidence: dict[str, Any],
    source: str,
) -> ActionCandidate:
    pending_goal_family = str(evidence.get("pending_goal_family") or "unknown")
    binding_type = _binding_type(tool, value)
    postcondition = _postcondition(tool, arg_name, binding_type=binding_type)
    risk_score, risk_flags = _candidate_risk(
        tool,
        source=source,
        postcondition=postcondition,
        pending_goal_family=pending_goal_family,
    )
    args = {arg_name: value} if arg_name and value is not None else {}
    bindings = (
        {
            arg_name: {
                "source": source,
                "value": value,
                "evidence": evidence,
            }
        }
        if arg_name and value is not None
        else {}
    )
    return ActionCandidate(
        tool=tool,
        args=args,
        arg_bindings=bindings,
        recommended_tools=[tool],
        reason=reason,
        evidence=evidence,
        binding_source=source,
        postcondition=postcondition,
        trajectory_risk_score=risk_score,
        trajectory_risk_flags=risk_flags,
        binding_type=binding_type,
        intervention_mode=_intervention_mode(risk_score),
        pending_goal_family=pending_goal_family,
    )


def _multi_arg_candidate(
    tool: str,
    args: dict[str, Any],
    *,
    reason: str,
    evidence: dict[str, Any],
    source: str,
) -> ActionCandidate:
    pending_goal_family = str(evidence.get("pending_goal_family") or "unknown")
    binding_type = "path" if tool in {"cp", "mv", "move_file", "copy_file"} else "unknown"
    target_arg = "destination" if "destination" in args else (next(iter(args.keys())) if args else "")
    postcondition = _postcondition(tool, target_arg, binding_type=binding_type)
    risk_score, risk_flags = _candidate_risk(
        tool,
        source=source,
        postcondition=postcondition,
        pending_goal_family=pending_goal_family,
    )
    bindings = {
        name: {
            "source": source,
            "value": value,
            "evidence": evidence,
        }
        for name, value in args.items()
    }
    return ActionCandidate(
        tool=tool,
        args=args,
        arg_bindings=bindings,
        recommended_tools=[tool],
        reason=reason,
        evidence=evidence,
        binding_source=source,
        postcondition=postcondition,
        trajectory_risk_score=risk_score,
        trajectory_risk_flags=risk_flags,
        binding_type=binding_type,
        intervention_mode=_intervention_mode(risk_score),
        pending_goal_family=pending_goal_family,
    )


def _tool_matches_pending_goal(tool: str, pending_goal_family: str) -> bool:
    expected = {
        "cat": "read_content",
        "touch": "create_file",
        "mkdir": "create_directory",
        "grep": "search",
        "find": "search",
        "mv": "move_or_copy",
        "cp": "move_or_copy",
        "move_file": "move_or_copy",
        "copy_file": "move_or_copy",
    }.get(tool)
    return expected is None or expected == pending_goal_family


def _candidate_allowed(tool: str, value: str | None, *, lowered_user_text: str, pending_goal_family: str) -> bool:
    if not value:
        return False
    if not _tool_matches_pending_goal(tool, pending_goal_family):
        return False
    if tool == "mkdir" and _looks_like_file(value):
        return False
    if tool == "cat" and (pending_goal_family != "read_content" or not _looks_like_file(value)):
        return False
    if tool == "touch" and not _looks_like_file(value):
        return pending_goal_family == "create_file" and any(token in lowered_user_text for token in ["file", "todo", "marker", "note"])
    return True


def _effective_pending_goal(state: ToolState) -> str:
    if state.pending_goal_family and state.pending_goal_family != "unknown":
        return state.pending_goal_family
    lowered = state.latest_user_text.lower()
    if state.user_intent_family == "read_file_content":
        return "read_content"
    if state.user_intent_family == "final_answer_allowed":
        return "final_answer"
    if state.user_intent_family == "move_or_copy":
        return "move_or_copy"
    if state.user_intent_family == "explicit_literal_action":
        if any(token in lowered for token in ["directory", "folder", "dir"]):
            return "create_directory"
        return "create_file"
    if state.user_intent_family == "path_action":
        return "create_file"
    return "unknown"


def generate_action_candidates(state: ToolState, tool_schemas: dict[str, dict[str, Any]] | None = None) -> list[ActionCandidate]:
    schemas = tool_schemas or state.tool_schemas
    state.tool_schemas = schemas
    if state.stop_allowed:
        return []

    pending_goal_family = _effective_pending_goal(state)
    candidates: list[ActionCandidate] = []
    if pending_goal_family == "read_content" and state.user_intent_family == "read_file_content" and _has_tool(state, "cat"):
        file_name, source, evidence = _read_file_value(state)
        if file_name:
            arg_name = _first_required_arg(schemas["cat"], ["file_name", "filename", "path"])
            candidates.append(
                _candidate(
                    "cat",
                    arg_name,
                    file_name,
                    reason="prior find/list output has a concrete match and the user asks to read content",
                    evidence={**evidence, "pending_goal_family": pending_goal_family},
                    source=source,
                )
            )
            return candidates

    lowered = state.latest_user_text.lower()
    if state.user_intent_family in {"explicit_literal_action", "move_or_copy"}:
        if pending_goal_family == "move_or_copy":
            tool = ""
            if any(token in lowered for token in ["copy", "duplicate"]) and _has_tool(state, "cp"):
                tool = "cp"
            elif any(token in lowered for token in ["move", "rename"]) and _has_tool(state, "mv"):
                tool = "mv"
            source, destination, binding_source, evidence = _move_copy_values(state)
            if tool and source and destination:
                arg_names = _ordered_args(schemas[tool], ["source", "src", "from", "file_name", "destination", "dest", "target", "to"])
                if len(arg_names) >= 2:
                    args = {arg_names[0]: source, arg_names[1]: destination}
                    candidates.append(
                        _multi_arg_candidate(
                            tool,
                            args,
                            reason="explicit source and destination literals ground a move/copy next action",
                            evidence={**evidence, "pending_goal_family": pending_goal_family},
                            source=binding_source,
                        )
                    )
                    return candidates
        if "lookup" in lowered and _has_tool(state, "lookup_id"):
            tool = "lookup_id"
            arg_name = _first_required_arg(schemas[tool], ["item_id", "id"])
            value = _literal_for_tool(state, tool)
        elif "delete" in lowered and _has_tool(state, "delete_file"):
            tool = "delete_file"
            arg_name = _first_required_arg(schemas[tool], ["file_name", "filename", "path"])
            value = _literal_for_tool(state, tool)
        elif any(token in lowered for token in ["directory", "folder", "dir"]) and _has_tool(state, "mkdir"):
            tool = "mkdir"
            arg_name = _first_required_arg(schemas[tool], ["dir_name", "directory", "path"])
            value = _literal_for_tool(state, tool)
        elif any(token in lowered for token in ["create", "add"]) and _has_tool(state, "touch"):
            tool = "touch"
            arg_name = _first_required_arg(schemas[tool], ["file_name", "filename", "path"])
            value = _literal_for_tool(state, tool)
        elif pending_goal_family == "read_content" and _has_tool(state, "cat"):
            tool = "cat"
            arg_name = _first_required_arg(schemas[tool], ["file_name", "filename", "path"])
            value = _literal_for_tool(state, tool)
        else:
            tool = ""
            arg_name = None
            value = None
        if tool and value and _candidate_allowed(tool, value, lowered_user_text=lowered, pending_goal_family=pending_goal_family):
            candidates.append(
                _candidate(
                    tool,
                    arg_name,
                    value,
                    reason="explicit literal in user request grounds the next tool argument",
                    evidence={"explicit_literals": state.explicit_literals, "intent": state.user_intent_family, "pending_goal_family": pending_goal_family},
                    source="explicit_literal",
                )
            )
            return candidates

    if state.user_intent_family == "path_action":
        if any(token in lowered for token in ["directory", "folder"]) and _has_tool(state, "mkdir"):
            tool = "mkdir"
            arg_name = _first_required_arg(schemas[tool], ["dir_name", "directory", "path"])
            value = "logs" if "logs" in lowered else "archive"
        elif any(token in lowered for token in ["file", "todo", "marker"]) and _has_tool(state, "touch"):
            tool = "touch"
            arg_name = _first_required_arg(schemas[tool], ["file_name", "filename", "path"])
            value = "TODO.md" if "todo" in lowered else "marker.txt"
        elif pending_goal_family == "read_content" and _has_tool(state, "cat"):
            tool = "cat"
            arg_name = _first_required_arg(schemas[tool], ["file_name", "filename", "path"])
            value = "README.md" if "readme" in lowered else None
        else:
            tool = ""
            arg_name = None
            value = None
        if tool and value and _candidate_allowed(tool, value, lowered_user_text=lowered, pending_goal_family=pending_goal_family):
            candidates.append(
                _candidate(
                    tool,
                    arg_name,
                    value,
                    reason="prior cwd/listing output grounds a path-sensitive next action",
                    evidence={"last_tool": state.last_tool, "prior_output_keys": state.prior_output_keys, "pending_goal_family": pending_goal_family},
                    source="prior_tool_output.cwd_or_listing",
                )
            )
    return candidates
