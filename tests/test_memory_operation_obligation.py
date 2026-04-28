from __future__ import annotations

import json
from pathlib import Path

import scripts.diagnose_memory_operation_obligation as mem


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _trace(path: Path, *, user: str, tools: list[str], calls: list[tuple[str, str]] | None = None) -> None:
    messages = [{"role": "user", "content": user}]
    for idx, (name, output) in enumerate(calls or []):
        messages.append({"type": "function_call", "name": name, "arguments": "{}", "call_id": f"call_{idx}"})
        messages.append({"type": "function_call_output", "call_id": f"call_{idx}", "output": output})
    _wj(path, {
        "request_original": {
            "input": messages,
            "tools": [{"name": tool, "parameters": {"type": "object", "properties": {}}} for tool in tools],
        },
        "validation": {"failure_labels": ["(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)"], "repair_kinds": []},
    })


def test_memory_retrieve_obligation_candidate_when_memory_intent_unsatisfied(tmp_path: Path) -> None:
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "one.json",
        user="What magazine does my kitchen look like a page out of?",
        tools=["archival_memory_key_search", "archival_memory_retrieve", "core_memory_retrieve"],
    )

    report = mem.evaluate(tmp_path)

    assert report["candidate_count"] == 1
    row = report["candidate_records"][0]
    assert row["operation"] == "retrieve"
    assert set(row["recommended_tools"]) == {"archival_memory_retrieve", "archival_memory_key_search", "core_memory_retrieve"}
    assert row["retention_eligibility"] == "diagnostic_only_until_family_review"
    assert row["runtime_enabled"] is False
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []


def test_memory_obligation_accepts_weak_lookup_for_second_pass_retrieve(tmp_path: Path) -> None:
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "one.json",
        user="What magazine does my kitchen look like a page out of?",
        tools=["archival_memory_key_search", "archival_memory_retrieve"],
        calls=[("archival_memory_key_search", json.dumps({"keys": ["kitchen"]}))],
    )

    report = mem.evaluate(tmp_path)

    assert report["candidate_count"] == 1
    assert report["candidate_records"][0]["memory_witness_strength"] == "weak_lookup_witness"


def test_memory_obligation_rejects_delete_until_reviewed(tmp_path: Path) -> None:
    _trace(
        tmp_path / "memory_rec_sum" / "baseline" / "traces" / "one.json",
        user="Forget my old address.",
        tools=["memory_clear", "memory_retrieve"],
    )

    report = mem.evaluate(tmp_path)

    assert report["candidate_count"] == 0
    assert report["rejection_reason_counts"]["delete_operation_requires_explicit_reviewer_approval"] == 1


def test_memory_obligation_rejects_strong_value_witness(tmp_path: Path) -> None:
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "strong.json",
        user="What magazine does my kitchen look like a page out of?",
        tools=["archival_memory_key_search", "archival_memory_retrieve"],
        calls=[("archival_memory_retrieve", json.dumps({"value": "Architectural Digest"}))],
    )

    report = mem.evaluate(tmp_path)

    assert report["candidate_count"] == 0
    assert report["rejection_reason_counts"]["memory_postcondition_already_satisfied"] == 1
