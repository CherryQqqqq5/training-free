from __future__ import annotations

import json
from pathlib import Path

import scripts.diagnose_postcondition_policy_negative_controls as neg


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _trace(path: Path, *, user: str, labels: list[str], predicates: list[str], rule_hits: list[str], tools: list[str], include_tool_output: bool = True) -> None:
    input_messages = [{"role": "user", "content": user}]
    if include_tool_output:
        input_messages.append({"type": "function_call_output", "call_id": "call_1", "output": "None"})
    _wj(path, {
        "request_original": {
            "input": input_messages,
            "tools": [{"name": tool, "parameters": {"type": "object", "properties": {}}} for tool in tools],
        },
        "validation": {
            "failure_labels": labels,
            "request_predicates": predicates,
            "rule_hits": rule_hits,
        },
    })


def test_negative_controls_bucket_rejected_traces_without_activation(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    _wj(manifest, {"runtime_enabled": False, "candidate_commands": [], "planned_commands": []})
    _trace(
        tmp_path / "run" / "traces" / "not_no_tool.json",
        user="Please read report.txt.",
        labels=["(OTHER,FAILURE)"],
        predicates=["prior_tool_outputs_present", "tools_available"],
        rule_hits=["rule1"],
        tools=["cat"],
    )
    _trace(
        tmp_path / "run" / "traces" / "no_prior.json",
        user="Please read report.txt.",
        labels=["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
        predicates=["tools_available"],
        rule_hits=["rule1"],
        tools=["cat"],
        include_tool_output=False,
    )
    _trace(
        tmp_path / "run" / "traces" / "missing_tool.json",
        user="Please search for budget analysis.",
        labels=["(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)"],
        predicates=["prior_tool_outputs_present", "tools_available"],
        rule_hits=["rule1"],
        tools=["cat"],
    )

    report = neg.evaluate(tmp_path, manifest)

    assert report["negative_control_audit_ready"] is True
    assert report["negative_control_activation_count"] == 0
    assert report["bucket_counts"] == {
        "missing_recommended_tool": 1,
        "no_prior_observation": 1,
        "no_toolless_failure_slice": 1,
    }
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []


def test_negative_control_audit_requires_manifest_runtime_disabled(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    _wj(manifest, {"runtime_enabled": True, "candidate_commands": [], "planned_commands": []})
    _trace(
        tmp_path / "run" / "traces" / "not_no_tool.json",
        user="Please read report.txt.",
        labels=["(OTHER,FAILURE)"],
        predicates=["prior_tool_outputs_present", "tools_available"],
        rule_hits=["rule1"],
        tools=["cat"],
    )

    report = neg.evaluate(tmp_path, manifest)

    assert report["negative_control_audit_ready"] is False
    assert report["candidate_manifest_runtime_enabled"] is True
