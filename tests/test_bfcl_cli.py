from __future__ import annotations

from grc.utils.bfcl_request_policy import apply_bfcl_fc_request_policy
from grc.utils.bfcl_request_policy import apply_bfcl_memory_request_policy

from bfcl_eval.model_handler.base_handler import BaseHandler
from scripts.run_bfcl_cli import _preserve_decoded_execution_output_shape
from scripts.run_bfcl_exact_2id_generate_smoke import _classify_result_for_run_id


def test_apply_fc_request_policy_sets_function_object_tool_choice_for_single_tool(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy(
        {"model": "m", "tools": [{"type": "function", "function": {"name": "touch"}}]}
    )

    assert updated["tool_choice"] == {"type": "function", "function": {"name": "touch"}}


def test_apply_fc_request_policy_respects_tool_choice_opt_out(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "0")

    updated = apply_bfcl_fc_request_policy({"model": "m", "tools": [{"type": "function"}]})

    assert "tool_choice" not in updated
    assert updated["max_tokens"] == 4096
    assert updated["temperature"] == 0
    assert updated["stream"] is False


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


def test_apply_fc_request_policy_keeps_required_for_multiple_tools(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy(
        {
            "model": "m",
            "tools": [
                {"type": "function", "function": {"name": "first"}},
                {"type": "function", "function": {"name": "second"}},
            ],
        }
    )

    assert updated["tool_choice"] == "required"


def test_apply_fc_request_policy_normalizes_schema_local_additional_properties(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy(
        {
            "model": "m",
            "tools": [
                {
                    "name": "touch",
                    "description": "unit fixture",
                    "parameters": {
                        "type": "object",
                        "properties": {"nested": {"type": "object", "properties": {}}},
                    },
                }
            ],
            "max_completion_tokens": 128,
        }
    )

    tool = updated["tools"][0]
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "touch"
    assert tool["function"]["parameters"]["additionalProperties"] is False
    assert tool["function"]["parameters"]["properties"]["nested"]["additionalProperties"] is False
    assert updated["max_tokens"] == 128
    assert "max_completion_tokens" not in updated
    assert updated["temperature"] == 0
    assert updated["stream"] is False


def test_apply_fc_request_policy_preserves_existing_additional_properties(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy(
        {
            "model": "m",
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "touch",
                        "parameters": {"type": "object", "additionalProperties": {"type": "string"}},
                    },
                }
            ],
        }
    )

    assert updated["tools"][0]["function"]["parameters"]["additionalProperties"] == {"type": "string"}


def test_apply_fc_request_policy_responses_path_uses_max_output_tokens(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy(
        {
            "model": "m",
            "tools": [{"type": "function", "function": {"name": "touch"}}],
            "max_tokens": 256,
        },
        api_path="responses",
    )

    assert updated["max_output_tokens"] == 256
    assert "max_tokens" not in updated
    assert "max_completion_tokens" not in updated


def test_apply_fc_request_policy_responses_path_converts_max_completion_tokens(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy(
        {
            "model": "m",
            "tools": [{"type": "function", "function": {"name": "touch"}}],
            "max_completion_tokens": 96,
        },
        api_path="responses",
    )

    assert updated["max_output_tokens"] == 96
    assert "max_tokens" not in updated
    assert "max_completion_tokens" not in updated


def test_apply_fc_request_policy_chat_path_keeps_max_tokens(monkeypatch):
    monkeypatch.setenv("GRC_BFCL_FORCE_TOOL_CHOICE", "1")

    updated = apply_bfcl_fc_request_policy(
        {
            "model": "m",
            "tools": [{"type": "function", "function": {"name": "touch"}}],
            "max_tokens": 256,
        },
        api_path="chat_completions",
    )

    assert updated["max_tokens"] == 256
    assert "max_output_tokens" not in updated


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



def _write_with_patched_base_handler(tmp_path, entry):
    handler = object.__new__(BaseHandler)
    handler.registry_dir_name = "offline_model"
    BaseHandler.write(handler, entry, tmp_path, update_mode=False)
    return list(tmp_path.rglob("*.json"))


def test_decoded_execution_nonempty_materializes_nonempty_result_shape(tmp_path):
    entry = {
        "id": "web_search_base_0",
        "result": [["response_shape_only"]],
        "inference_log": [
            {
                "step_0": [
                    {
                        "role": "handler_log",
                        "content": "Successfully decoded model response.",
                        "model_response_decoded": ["decoded_execution_shape"],
                    }
                ]
            }
        ],
    }

    patched = _preserve_decoded_execution_output_shape(entry)
    assert patched["grc_decoded_execution_output_shape"] == {
        "shape_label": "execution_list_nonempty",
        "decoded_output_count": 1,
        "function_call_shape_present": True,
    }

    files = _write_with_patched_base_handler(tmp_path, entry)
    assert len(files) == 1
    rel = files[0].relative_to(tmp_path / "offline_model")
    assert len(rel.parts) >= 2
    assert "web_search_base" in files[0].name
    classification = _classify_result_for_run_id("web_search_base_0", tmp_path)
    assert classification["tool_call_detected"] is True
    assert classification["status"] == "generated"


def test_true_empty_decoded_output_remains_empty(tmp_path):
    entry = {
        "id": "web_search_base_0",
        "result": [[""]],
        "inference_log": [
            {
                "step_0": [
                    {
                        "role": "handler_log",
                        "content": "Empty response from the model. Proceed to next turn.",
                        "model_response_decoded": [],
                    }
                ]
            }
        ],
    }

    patched = _preserve_decoded_execution_output_shape(entry)
    assert "grc_decoded_execution_output_shape" not in patched
    _write_with_patched_base_handler(tmp_path, entry)
    classification = _classify_result_for_run_id("web_search_base_0", tmp_path)
    assert classification["empty_model_response_detected"] is True
    assert classification["tool_call_detected"] is False


def test_protocol_exception_result_remains_protocol_error(tmp_path):
    entry = {
        "id": "web_search_base_0",
        "result": "Error during inference: protocol failure",
        "inference_log": [
            {
                "step_0": [
                    {
                        "role": "handler_log",
                        "content": "Error decoding the model response. Proceed to next turn.",
                        "error": "ProtocolError",
                    }
                ]
            }
        ],
    }

    patched = _preserve_decoded_execution_output_shape(entry)
    assert "grc_decoded_execution_output_shape" not in patched
    _write_with_patched_base_handler(tmp_path, entry)
    classification = _classify_result_for_run_id("web_search_base_0", tmp_path)
    assert classification["protocol_error_detected"] is True
    assert classification["status"] == "protocol_error"
