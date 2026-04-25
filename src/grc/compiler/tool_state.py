from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any

from grc.utils.jsonfix import parse_loose_json
from grc.utils.tool_schema import tool_map_from_tools_payload

_QUOTED_LITERAL_RE = re.compile(r"'([^'\n]{1,160})'|\"([^\"\n]{1,160})\"")
_FILE_LITERAL_RE = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9_.-]*\.[A-Za-z0-9]{1,10}\b")
_ID_LITERAL_RE = re.compile(r"\b[A-Z]-\d{2,}\b")
_PATH_SEGMENT_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
_REASONABLE_FILE_EXTENSIONS = {
    "cfg",
    "conf",
    "csv",
    "html",
    "ini",
    "json",
    "log",
    "md",
    "pdf",
    "py",
    "sh",
    "tar",
    "ts",
    "txt",
    "xml",
    "yaml",
    "yml",
    "zip",
}
_FINAL_ANSWER_TOKENS = ("summarize", "what is", "report whether", "give me", "confirm")
_READ_TOKENS = ("read", "open", "show", "display", "contents", "content")
_WRITE_TOKENS = ("write", "modify", "replace", "update", "append", "put", "edit")
_MOVE_COPY_TOKENS = ("move", "copy", "rename", "duplicate")
_SEARCH_TOKENS = ("search", "find", "grep", "locate", "match", "matches")
_SUBMIT_TOKENS = ("post", "send", "submit", "ticket", "email")
_CREATE_TOKENS = ("create", "make", "add", "touch")
_REFERENCE_LITERAL_VALUES = {
    "it",
    "this",
    "that",
    "this one",
    "that one",
    "the one",
    "same one",
    "previous one",
}


@dataclass
class PriorToolOutput:
    tool_name: str | None = None
    content: Any = None
    keys: list[str] = field(default_factory=list)


@dataclass
class ToolState:
    available_tools: list[str] = field(default_factory=list)
    tool_schemas: dict[str, dict[str, Any]] = field(default_factory=dict)
    latest_user_text: str = ""
    prior_tool_outputs: list[PriorToolOutput] = field(default_factory=list)
    prior_output_keys: list[str] = field(default_factory=list)
    explicit_literals: list[str] = field(default_factory=list)
    last_tool: str | None = None
    user_intent_family: str = "unknown"
    stop_allowed: bool = False
    pending_goal_family: str = "unknown"


def _request_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    request = payload.get("request")
    if isinstance(request, dict):
        return request
    request = payload.get("request_original")
    if isinstance(request, dict):
        return request
    return payload if isinstance(payload, dict) else {}


def _message_candidates(request: dict[str, Any]) -> list[Any]:
    candidates: list[Any] = []
    for key in ("messages", "input"):
        value = request.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    return candidates


def _stringify_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if content is None:
        return ""
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception:
        return str(content)


def _parse_tool_content(content: Any) -> Any:
    if not isinstance(content, str):
        return content
    stripped = content.strip()
    if not stripped:
        return ""
    try:
        return parse_loose_json(stripped)
    except Exception:
        return content


def _keys_from_content(content: Any) -> list[str]:
    if isinstance(content, dict):
        return [str(key) for key in content.keys()]
    return []


def _collect_explicit_literals(text: str) -> list[str]:
    literals: list[str] = []
    for match in _QUOTED_LITERAL_RE.finditer(text):
        value = next((group for group in match.groups() if group), "")
        if value.strip().lower() in _REFERENCE_LITERAL_VALUES:
            continue
        if value and value not in literals:
            literals.append(value)
    for match in _FILE_LITERAL_RE.finditer(text):
        value = match.group(0)
        if value not in literals:
            literals.append(value)
    for match in _ID_LITERAL_RE.finditer(text):
        value = match.group(0)
        if value not in literals:
            literals.append(value)
    return literals


def is_strict_file_literal(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    if not text or len(text) > 120 or text.endswith("/"):
        return False
    if any(ch.isspace() for ch in text):
        return False
    if any(ch in text for ch in [":", ";", "!", "?", '"', "'", "`", "{", "}", "[", "]", "(", ")"]):
        return False
    parts = [part for part in text.split("/") if part]
    if not parts:
        return False
    for part in parts:
        if part in {".", ".."} or not _PATH_SEGMENT_RE.fullmatch(part):
            return False
    basename = parts[-1]
    if len(basename) > 80 or "." not in basename:
        return False
    stem, ext = basename.rsplit(".", 1)
    if not stem or not ext or len(ext) > 10:
        return False
    if ext.lower() not in _REASONABLE_FILE_EXTENSIONS:
        return False
    return True


def _has_any(lowered: str, tokens: tuple[str, ...]) -> bool:
    return any(token in lowered for token in tokens)


def _pending_goal_family(text: str, prior_outputs: list[PriorToolOutput]) -> str:
    lowered = text.lower()
    if _has_any(lowered, _FINAL_ANSWER_TOKENS):
        return "final_answer"
    if _has_any(lowered, _SUBMIT_TOKENS):
        return "submit_or_send"
    if _has_any(lowered, _MOVE_COPY_TOKENS):
        return "move_or_copy"
    if "compare" in lowered or "diff" in lowered:
        return "compare"
    if _has_any(lowered, _WRITE_TOKENS):
        return "write_content"
    if _has_any(lowered, _CREATE_TOKENS):
        if any(token in lowered for token in ["directory", "folder", "dir"]):
            return "create_directory"
        return "create_file"
    if _has_any(lowered, _READ_TOKENS):
        return "read_content"
    if _has_any(lowered, _SEARCH_TOKENS):
        return "search"
    if prior_outputs and any(token in lowered for token in ["file", "todo", "marker", "directory", "folder"]):
        return "create_file"
    return "unknown"


def _classify_intent(text: str, prior_outputs: list[PriorToolOutput]) -> str:
    lowered = text.lower()
    if "lookup" in lowered and any(_collect_explicit_literals(text)):
        return "explicit_literal_action"
    goal = _pending_goal_family(text, prior_outputs)
    if goal == "final_answer":
        return "final_answer_allowed"
    if goal == "read_content":
        return "read_file_content"
    if goal in {"create_file", "create_directory", "write_content", "move_or_copy", "submit_or_send"}:
        if any(_collect_explicit_literals(text)):
            return "explicit_literal_action"
        if prior_outputs:
            return "path_action"
    if goal == "search" and prior_outputs:
        return "path_action"
    return "unknown"


def _basename(value: str) -> str:
    return PurePath(value).name or value


def extract_tool_state(payload: dict[str, Any]) -> ToolState:
    request = _request_from_payload(payload)
    tool_schemas = tool_map_from_tools_payload(request.get("tools", []))
    latest_user_text = ""
    prior_outputs: list[PriorToolOutput] = []

    for item in _message_candidates(request):
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        if role == "user":
            latest_user_text = _stringify_content(item.get("content"))
        if role == "tool" or item.get("type") == "function_call_output":
            parsed = _parse_tool_content(item.get("content") if "content" in item else item.get("output"))
            prior_outputs.append(
                PriorToolOutput(
                    tool_name=item.get("name"),
                    content=parsed,
                    keys=_keys_from_content(parsed),
                )
            )

    output_keys: list[str] = []
    for output in prior_outputs:
        for key in output.keys:
            if key not in output_keys:
                output_keys.append(key)

    intent = _classify_intent(latest_user_text, prior_outputs)
    pending_goal = _pending_goal_family(latest_user_text, prior_outputs)
    state = ToolState(
        available_tools=sorted(tool_schemas.keys()),
        tool_schemas=tool_schemas,
        latest_user_text=latest_user_text,
        prior_tool_outputs=prior_outputs,
        prior_output_keys=output_keys,
        explicit_literals=_collect_explicit_literals(latest_user_text),
        last_tool=prior_outputs[-1].tool_name if prior_outputs else None,
        user_intent_family=intent,
        stop_allowed=intent == "final_answer_allowed",
        pending_goal_family=pending_goal,
    )
    return state


def first_match_basename(state: ToolState) -> str | None:
    for output in reversed(state.prior_tool_outputs):
        content = output.content
        if isinstance(content, dict):
            matches = content.get("matches")
            if isinstance(matches, list) and matches:
                first = matches[0]
                if isinstance(first, str) and first.strip():
                    return _basename(first.strip())
    return None
