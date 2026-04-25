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
    postcondition: dict[str, Any] = field(default_factory=dict)
    trajectory_risk_score: int = 0
    trajectory_risk_flags: list[str] = field(default_factory=list)
    binding_type: str = "unknown"
    intervention_mode: str = "guidance"

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


def _read_file_value(state: ToolState) -> tuple[str | None, str, dict[str, Any]]:
    match_value = first_match_basename(state)
    if match_value:
        return (
            match_value,
            "prior_tool_output.matches[0]|basename",
            {"last_tool": state.last_tool, "prior_output_keys": state.prior_output_keys},
        )
    file_literals = [item for item in state.explicit_literals if "." in item]
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
            if not isinstance(entry, str) or "." not in entry:
                continue
            basename = entry.rstrip("/").split("/")[-1]
            stem = basename.rsplit(".", 1)[0].lower()
            if basename.lower() in lowered or stem in lowered:
                return (
                    basename,
                    "prior_tool_output.entries|basename",
                    {"last_tool": state.last_tool, "prior_output_keys": state.prior_output_keys},
                )
    return None, "", {}


def _looks_like_file(value: str | None) -> bool:
    if not value:
        return False
    basename = value.rstrip("/").split("/")[-1]
    if basename in {"", ".", ".."}:
        return False
    return "." in basename and not value.endswith("/")


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


def _candidate_risk(tool: str, *, source: str, postcondition: dict[str, Any]) -> tuple[int, list[str]]:
    flags: list[str] = []
    score = 0
    if tool in {"cat", "touch", "mkdir"}:
        flags.append("trajectory_sensitive_tool")
        score += 2
    if not postcondition:
        flags.append("postcondition_missing")
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
    binding_type = _binding_type(tool, value)
    postcondition = _postcondition(tool, arg_name, binding_type=binding_type)
    risk_score, risk_flags = _candidate_risk(tool, source=source, postcondition=postcondition)
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
    )


def _candidate_allowed(tool: str, value: str | None, *, lowered_user_text: str) -> bool:
    if not value:
        return False
    if tool == "mkdir" and _looks_like_file(value):
        return False
    if tool == "cat" and not _looks_like_file(value):
        return False
    if tool == "touch" and not _looks_like_file(value):
        return any(token in lowered_user_text for token in ["file", "todo", "marker", "note"])
    return True


def generate_action_candidates(state: ToolState, tool_schemas: dict[str, dict[str, Any]] | None = None) -> list[ActionCandidate]:
    schemas = tool_schemas or state.tool_schemas
    state.tool_schemas = schemas
    if state.stop_allowed:
        return []

    candidates: list[ActionCandidate] = []
    if state.user_intent_family == "read_file_content" and _has_tool(state, "cat"):
        file_name, source, evidence = _read_file_value(state)
        if file_name:
            arg_name = _first_required_arg(schemas["cat"], ["file_name", "filename", "path"])
            candidates.append(
                _candidate(
                    "cat",
                    arg_name,
                    file_name,
                    reason="prior find/list output has a concrete match and the user asks to read content",
                    evidence=evidence,
                    source=source,
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
        if tool and value and _candidate_allowed(tool, value, lowered_user_text=lowered):
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
        if tool and value and _candidate_allowed(tool, value, lowered_user_text=lowered):
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
