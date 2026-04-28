from __future__ import annotations

import json
from pathlib import Path

import scripts.build_memory_operation_obligation_approval as mem_approval
import scripts.check_memory_operation_obligation as mem_check
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



def test_memory_approval_manifest_evaluates_negative_controls_and_sanitizes_support(tmp_path: Path) -> None:
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "candidate.json",
        user="What magazine does my kitchen look like a page out of?",
        tools=["archival_memory_key_search", "archival_memory_retrieve"],
    )
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "weak.json",
        user="What magazine does my kitchen look like a page out of?",
        tools=["archival_memory_key_search", "archival_memory_retrieve"],
        calls=[("archival_memory_key_search", json.dumps({"keys": ["kitchen"]}))],
    )
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "no_tools.json",
        user="What magazine does my kitchen look like a page out of?",
        tools=["calculator"],
    )
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "no_intent.json",
        user="Please add 2 and 2.",
        tools=["archival_memory_key_search", "archival_memory_retrieve"],
    )
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "strong.json",
        user="What magazine does my kitchen look like a page out of?",
        tools=["archival_memory_key_search", "archival_memory_retrieve"],
        calls=[("archival_memory_retrieve", json.dumps({"value": "Architectural Digest"}))],
    )
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "empty.json",
        user="What magazine does my kitchen look like a page out of?",
        tools=["archival_memory_key_search", "archival_memory_retrieve"],
        calls=[("archival_memory_key_search", "[]")],
    )
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "delete.json",
        user="Forget my old address.",
        tools=["memory_clear", "memory_retrieve"],
    )

    audit = mem.evaluate(tmp_path)
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")

    outputs = mem_approval.evaluate(audit_path)
    negative = outputs["negative_report"]
    approval = outputs["approval_manifest"]

    assert negative["negative_control_audit_passed"] is True
    assert negative["negative_control_evaluations"]["no_memory_tools"]["evaluated_count"] == 1
    assert negative["negative_control_evaluations"]["no_memory_tools"]["activation_count"] == 0
    assert negative["negative_control_evaluations"]["no_memory_intent"]["evaluated_count"] == 1
    assert negative["negative_control_evaluations"]["strong_value_witness"]["evaluated_count"] == 1
    assert negative["negative_control_evaluations"]["empty_or_error_witness"]["evaluated_count"] == 1
    assert negative["negative_control_evaluations"]["delete_clear_forget"]["evaluated_count"] == 1
    assert approval["approval_manifest_ready_for_review"] is True
    assert approval["first_pass_review_candidate_count"] == 1
    assert approval["second_pass_review_candidate_count"] == 1
    assert approval["compiler_input_eligible_count"] == 0
    serialized = json.dumps(approval["support_records"])
    assert "trace_relative_path" not in serialized
    assert "source_audit_record_pointer_debug_only" not in serialized
    assert "available_memory_tools" not in serialized
    assert approval["support_records"][1]["requires_separate_weak_witness_approval"] is True


def test_memory_checker_fails_empty_candidates_and_count_mismatch(tmp_path: Path) -> None:
    audit = {"candidate_count": 1, "candidate_records": [], "runtime_enabled": False, "candidate_commands": [], "planned_commands": []}
    audit_path = tmp_path / "audit.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")

    report = mem_check.evaluate(audit_path, None, None, require_approval_artifacts=False)

    assert report["memory_operation_obligation_check_passed"] is False
    checks = {failure["check"] for failure in report["failures"]}
    assert "candidate_records_present" in checks
    assert "candidate_count_matches_records" in checks


def test_memory_checker_passes_with_generated_negative_and_approval_artifacts(tmp_path: Path) -> None:
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "candidate.json",
        user="What magazine does my kitchen look like a page out of?",
        tools=["archival_memory_key_search", "archival_memory_retrieve"],
    )
    _trace(
        tmp_path / "memory_kv" / "baseline" / "traces" / "no_intent.json",
        user="Please add 2 and 2.",
        tools=["archival_memory_key_search", "archival_memory_retrieve"],
    )
    audit = mem.evaluate(tmp_path)
    audit_path = tmp_path / "audit.json"
    negative_path = tmp_path / "negative.json"
    approval_path = tmp_path / "approval.json"
    allowlist_path = tmp_path / "allowlist.json"
    audit_path.write_text(json.dumps(audit), encoding="utf-8")
    outputs = mem_approval.evaluate(audit_path)
    negative_path.write_text(json.dumps(outputs["negative_report"]), encoding="utf-8")
    approval_path.write_text(json.dumps(outputs["approval_manifest"]), encoding="utf-8")
    allowlist_path.write_text(json.dumps(outputs["compiler_allowlist"]), encoding="utf-8")

    report = mem_check.evaluate(audit_path, negative_path, approval_path, allowlist_path)

    assert report["memory_operation_obligation_check_passed"] is True
