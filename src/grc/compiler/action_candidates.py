from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from grc.compiler.tool_state import ToolState, first_match_basename


@dataclass
class ActionCandidate:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    arg_bindings: dict[str, dict[str, Any]] = field(default_factory=dict)
    recommended_tools: list[str] = field(default_factory=list)
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    binding_source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "args": self.args,
            "arg_bindings": self.arg_bindings,
            "recommended_tools": self.recommended_tools or [self.tool],
            "reason": self.reason,
            "evidence": self.evidence,
            "binding_source": self.binding_source,
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


def _literal_for_tool(state: ToolState, tool_name: str) -> str | None:
    if not state.explicit_literals:
        return None
    lowered = state.latest_user_text.lower()
    if tool_name == "lookup_id":
        return state.explicit_literals[0]
    file_literals = [item for item in state.explicit_literals if "." in item]
    if tool_name in {"cat", "delete_file", "touch"} and file_literals:
        return file_literals[0]
    if tool_name == "mkdir":
        return state.explicit_literals[0]
    if "read" in lowered or "open" in lowered:
        return state.explicit_literals[0]
    return state.explicit_literals[0]


def _candidate(tool: str, arg_name: str | None, value: str | None, *, reason: str, evidence: dict[str, Any], source: str) -> ActionCandidate:
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
    )


def generate_action_candidates(state: ToolState, tool_schemas: dict[str, dict[str, Any]] | None = None) -> list[ActionCandidate]:
    schemas = tool_schemas or state.tool_schemas
    state.tool_schemas = schemas
    if state.stop_allowed:
        return []

    candidates: list[ActionCandidate] = []
    if state.user_intent_family == "read_file_content" and _has_tool(state, "cat"):
        file_name = first_match_basename(state)
        if file_name:
            arg_name = _first_required_arg(schemas["cat"], ["file_name", "filename", "path"])
            candidates.append(
                _candidate(
                    "cat",
                    arg_name,
                    file_name,
                    reason="prior find/list output has a concrete match and the user asks to read content",
                    evidence={"last_tool": state.last_tool, "prior_output_keys": state.prior_output_keys},
                    source="prior_tool_output.matches[0]|basename",
                )
            )
            return candidates

    lowered = state.latest_user_text.lower()
    if state.user_intent_family == "explicit_literal_action":
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
        elif _has_tool(state, "cat"):
            tool = "cat"
            arg_name = _first_required_arg(schemas[tool], ["file_name", "filename", "path"])
            value = _literal_for_tool(state, tool)
        else:
            tool = ""
            arg_name = None
            value = None
        if tool and value:
            candidates.append(
                _candidate(
                    tool,
                    arg_name,
                    value,
                    reason="explicit literal in user request grounds the next tool argument",
                    evidence={"explicit_literals": state.explicit_literals, "intent": state.user_intent_family},
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
        elif _has_tool(state, "cat"):
            tool = "cat"
            arg_name = _first_required_arg(schemas[tool], ["file_name", "filename", "path"])
            value = "README.md" if "readme" in lowered else None
        else:
            tool = ""
            arg_name = None
            value = None
        if tool and value:
            candidates.append(
                _candidate(
                    tool,
                    arg_name,
                    value,
                    reason="prior cwd/listing output grounds a path-sensitive next action",
                    evidence={"last_tool": state.last_tool, "prior_output_keys": state.prior_output_keys},
                    source="prior_tool_output.cwd_or_listing",
                )
            )
    return candidates
