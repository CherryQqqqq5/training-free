from __future__ import annotations

import os
from typing import Iterable
from typing import Any


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() not in {"", "0", "false", "no", "off"}


_BFCL_MEMORY_POLICY_PREFIX = "[BFCL Memory Retrieval Policy]"
_BFCL_FINAL_ANSWER_CONTRACT = "For your final answer to the user, you must respond in this format:"
_BFCL_DEFAULT_MAX_TOKENS = 4096


def _message_has_tool_interaction(message: dict[str, Any]) -> bool:
    if not isinstance(message, dict):
        return False
    if message.get("role") == "tool":
        return True
    if message.get("tool_calls"):
        return True
    item_type = message.get("type")
    if item_type in {"function_call", "function_call_output"}:
        return True
    return False


def _history_has_tool_interaction(kwargs: dict[str, Any]) -> bool:
    for key in ("messages", "input"):
        value = kwargs.get(key)
        if not isinstance(value, list):
            continue
        if any(_message_has_tool_interaction(item) for item in value):
            return True
    return False


def _iter_messages(kwargs: dict[str, Any]) -> tuple[str, list[dict[str, Any]]] | tuple[None, list[Any]]:
    for key in ("messages", "input"):
        value = kwargs.get(key)
        if isinstance(value, list):
            return key, value
    return None, []


def _iter_text_contents(messages: Iterable[Any]) -> Iterable[str]:
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            yield content


def _is_memory_tool_name(name: str) -> bool:
    return name.startswith("core_memory_") or name.startswith("archival_memory_")


def _request_uses_memory_tools(kwargs: dict[str, Any]) -> bool:
    tools = kwargs.get("tools")
    if not isinstance(tools, list):
        return False
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function")
        if isinstance(function, dict):
            name = function.get("name")
            if isinstance(name, str) and _is_memory_tool_name(name):
                return True
        name = tool.get("name")
        if isinstance(name, str) and _is_memory_tool_name(name):
            return True
    return False


def _has_final_answer_contract(kwargs: dict[str, Any]) -> bool:
    _, messages = _iter_messages(kwargs)
    return any(_BFCL_FINAL_ANSWER_CONTRACT in text for text in _iter_text_contents(messages))


def _has_existing_memory_policy(kwargs: dict[str, Any]) -> bool:
    _, messages = _iter_messages(kwargs)
    return any(_BFCL_MEMORY_POLICY_PREFIX in text for text in _iter_text_contents(messages))


def _memory_policy_message() -> dict[str, str]:
    return {
        "role": "developer",
        "content": (
            f"{_BFCL_MEMORY_POLICY_PREFIX}\n"
            "- This is a memory-recall task. Answer from explicit memory facts only, not general advice.\n"
            "- Prefer the exact stored fact, phrase, number, range, or short span from memory/tool outputs over paraphrase.\n"
            "- If the first search result is weak, zero-score, or indirect, do another retrieval pass: try an alternate query, list keys, and retrieve the best candidate keys before answering.\n"
            "- Do not write speculative memory notes or mutate memory just because retrieval was inconclusive.\n"
            "- If the answer is still not explicit after retrieval, answer exactly: {'answer': 'I do not know', 'context': 'I do not know'}."
        ),
    }


def apply_bfcl_memory_request_policy(kwargs: dict[str, Any]) -> dict[str, Any]:
    updated = dict(kwargs)
    if not _env_flag("GRC_BFCL_MEMORY_RETRIEVAL_POLICY", "1"):
        return updated
    if not _request_uses_memory_tools(updated):
        return updated
    if not _has_final_answer_contract(updated):
        return updated
    if _has_existing_memory_policy(updated):
        return updated

    key, messages = _iter_messages(updated)
    if key is None:
        return updated
    updated[key] = [_memory_policy_message(), *messages]
    return updated


def _normalize_function_tool(tool: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(tool)
    function = normalized.get("function")
    if isinstance(function, dict):
        normalized["function"] = _normalize_function_definition(function)
        normalized.setdefault("type", "function")
        return normalized

    name = normalized.get("name")
    if not isinstance(name, str) or not name:
        return normalized
    function_payload: dict[str, Any] = {"name": name}
    for key in ("description", "parameters"):
        if key in normalized:
            function_payload[key] = normalized[key]
    return {"type": "function", "function": _normalize_function_definition(function_payload)}


def _normalize_function_definition(function: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(function)
    parameters = normalized.get("parameters")
    if isinstance(parameters, dict):
        normalized["parameters"] = _normalize_schema_object(parameters)
    return normalized


def _normalize_schema_object(schema: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(schema)
    if normalized.get("type") == "object":
        normalized.setdefault("additionalProperties", False)
    properties = normalized.get("properties")
    if isinstance(properties, dict):
        normalized["properties"] = {
            key: _normalize_schema_object(value) if isinstance(value, dict) else value
            for key, value in properties.items()
        }
    items = normalized.get("items")
    if isinstance(items, dict):
        normalized["items"] = _normalize_schema_object(items)
    return normalized


def _normalize_tools(tools: Any) -> list[Any]:
    if not isinstance(tools, list):
        return tools
    normalized: list[Any] = []
    for tool in tools:
        if isinstance(tool, dict):
            normalized.append(_normalize_function_tool(tool))
        else:
            normalized.append(tool)
    return normalized


def _function_tool_names(tools: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(tools, list):
        return names
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function")
        if isinstance(function, dict):
            name = function.get("name")
        else:
            name = tool.get("name")
        if isinstance(name, str) and name:
            names.append(name)
    return names


def _required_tool_choice_for_tools(tools: Any) -> str | dict[str, Any]:
    names = _function_tool_names(tools)
    if len(names) == 1:
        return {"type": "function", "function": {"name": names[0]}}
    return "required"


def _token_limit() -> int:
    return int(os.getenv("GRC_BFCL_MAX_TOKENS", str(_BFCL_DEFAULT_MAX_TOKENS)))


def _normalize_chat_token_fields(updated: dict[str, Any]) -> None:
    if "max_completion_tokens" in updated:
        updated.setdefault("max_tokens", updated.pop("max_completion_tokens"))
    updated.setdefault("max_tokens", _token_limit())


def _normalize_responses_token_fields(updated: dict[str, Any]) -> None:
    if "max_output_tokens" not in updated:
        if "max_tokens" in updated:
            updated["max_output_tokens"] = updated.pop("max_tokens")
        elif "max_completion_tokens" in updated:
            updated["max_output_tokens"] = updated.pop("max_completion_tokens")
        else:
            updated["max_output_tokens"] = _token_limit()
    else:
        updated.pop("max_tokens", None)
        updated.pop("max_completion_tokens", None)


def _normalize_openai_compatible_fields(updated: dict[str, Any], *, api_path: str = "chat_completions") -> None:
    if api_path == "responses":
        _normalize_responses_token_fields(updated)
    else:
        _normalize_chat_token_fields(updated)
    updated.setdefault("temperature", 0)
    updated.setdefault("stream", False)
    updated.setdefault("timeout", int(os.getenv("GRC_BFCL_TIMEOUT_SECONDS", "120")))


def apply_bfcl_fc_request_policy(kwargs: dict[str, Any], *, api_path: str = "chat_completions") -> dict[str, Any]:
    updated = dict(kwargs)
    if not updated.get("tools"):
        return updated

    updated["tools"] = _normalize_tools(updated.get("tools"))
    _normalize_openai_compatible_fields(updated, api_path=api_path)

    if (
        _env_flag("GRC_BFCL_FORCE_TOOL_CHOICE", "1")
        and not _history_has_tool_interaction(updated)
    ):
        updated.setdefault("tool_choice", _required_tool_choice_for_tools(updated.get("tools")))
    return updated
