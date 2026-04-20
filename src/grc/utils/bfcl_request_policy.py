from __future__ import annotations

import os
from typing import Iterable
from typing import Any


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() not in {"", "0", "false", "no", "off"}


_BFCL_MEMORY_POLICY_PREFIX = "[BFCL Memory Retrieval Policy]"
_BFCL_FINAL_ANSWER_CONTRACT = "For your final answer to the user, you must respond in this format:"


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


def apply_bfcl_fc_request_policy(kwargs: dict[str, Any]) -> dict[str, Any]:
    updated = dict(kwargs)
    if (
        updated.get("tools")
        and _env_flag("GRC_BFCL_FORCE_TOOL_CHOICE", "1")
        and not _history_has_tool_interaction(updated)
    ):
        updated.setdefault("tool_choice", "required")
    return updated
