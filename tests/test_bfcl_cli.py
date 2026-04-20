from __future__ import annotations

from grc.utils.bfcl_request_policy import apply_bfcl_fc_request_policy
from grc.utils.bfcl_request_policy import apply_bfcl_memory_request_policy


def test_apply_fc_request_policy_sets_required_tool_choice(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy({"model": "m", "tools": [{"type": "function"}]})

    assert updated["tool_choice"] == "required"


def test_apply_fc_request_policy_respects_opt_out(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "0")

    updated = apply_bfcl_fc_request_policy({"model": "m", "tools": [{"type": "function"}]})

    assert "tool_choice" not in updated


def test_apply_fc_request_policy_preserves_existing_tool_choice(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy(
        {"model": "m", "tools": [{"type": "function"}], "tool_choice": "auto"}
    )

    assert updated["tool_choice"] == "auto"


def test_apply_fc_request_policy_does_not_force_after_tool_message(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy(
        {
            "model": "m",
            "tools": [{"type": "function"}],
            "messages": [
                {"role": "user", "content": "q"},
                {"role": "assistant", "tool_calls": [{"id": "c1"}], "content": ""},
                {"role": "tool", "tool_call_id": "c1", "content": "{\"status\":\"ok\"}"},
            ],
        }
    )

    assert "tool_choice" not in updated


def test_apply_fc_request_policy_does_not_force_after_responses_function_output(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy(
        {
            "model": "m",
            "tools": [{"type": "function"}],
            "input": [
                {"role": "user", "content": "q"},
                {"type": "function_call", "id": "c1", "name": "touch", "arguments": "{}"},
                {"type": "function_call_output", "call_id": "c1", "output": "{\"status\":\"ok\"}"},
            ],
        }
    )

    assert "tool_choice" not in updated


def test_apply_memory_request_policy_injects_for_memory_recall(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_MEMORY_RETRIEVAL_POLICY", "1")

    updated = apply_bfcl_memory_request_policy(
        {
            "model": "m",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "archival_memory_key_search",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "For your final answer to the user, you must respond in this format: "
                        "{'answer': A short and precise answer to the question, "
                        "'context': A brief explanation of how you arrived at this answer or why it is correct}."
                    ),
                },
                {"role": "user", "content": "What did I say about vendor planning?"},
            ],
        }
    )

    assert updated["messages"][0]["role"] == "developer"
    assert "[BFCL Memory Retrieval Policy]" in updated["messages"][0]["content"]


def test_apply_memory_request_policy_skips_non_memory_tools(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_MEMORY_RETRIEVAL_POLICY", "1")

    updated = apply_bfcl_memory_request_policy(
        {
            "model": "m",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "touch",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            "messages": [
                {
                    "role": "system",
                    "content": "For your final answer to the user, you must respond in this format:",
                },
                {"role": "user", "content": "Create a file."},
            ],
        }
    )

    assert updated["messages"][0]["role"] == "system"


def test_apply_memory_request_policy_skips_without_contract(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_MEMORY_RETRIEVAL_POLICY", "1")

    updated = apply_bfcl_memory_request_policy(
        {
            "model": "m",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "core_memory_retrieve",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            "messages": [{"role": "user", "content": "What did I say?"}],
        }
    )

    assert updated["messages"][0]["role"] == "user"


def test_apply_memory_request_policy_skips_if_already_present(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_MEMORY_RETRIEVAL_POLICY", "1")

    updated = apply_bfcl_memory_request_policy(
        {
            "model": "m",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "core_memory_retrieve",
                        "parameters": {"type": "object"},
                    },
                }
            ],
            "messages": [
                {"role": "developer", "content": "[BFCL Memory Retrieval Policy]\n- Existing."},
                {
                    "role": "system",
                    "content": "For your final answer to the user, you must respond in this format:",
                },
                {"role": "user", "content": "What did I say?"},
            ],
        }
    )

    assert updated["messages"][0]["content"] == "[BFCL Memory Retrieval Policy]\n- Existing."
