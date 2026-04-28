from __future__ import annotations

import json
from pathlib import Path

import yaml

from grc.runtime.engine import RuleEngine
import scripts.build_postcondition_guided_runtime_smoke_adapter as builder
import scripts.check_postcondition_guided_runtime_smoke_readiness as readiness


def _write_policy_dir(policy_dir: Path) -> None:
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "policy_unit.yaml").write_text(yaml.safe_dump({
        "runtime_enabled": False,
        "candidate_commands": [],
        "planned_commands": [],
        "policy_units": [
            {
                "policy_unit_id": "postcondition_guided_read_content_soft_v1",
                "runtime_enabled": False,
                "tool_choice_mode": "soft",
                "exact_tool_choice": False,
                "trigger": {"postcondition_gap": "read_content"},
                "decision_policy": {"recommended_tools": ["cat"], "argument_policy": "no_argument_creation_or_binding", "capability_only": True},
            },
            {
                "policy_unit_id": "postcondition_guided_search_or_find_soft_v1",
                "runtime_enabled": False,
                "tool_choice_mode": "soft",
                "exact_tool_choice": False,
                "trigger": {"postcondition_gap": "search_or_find"},
                "decision_policy": {"recommended_tools": ["grep", "find"], "argument_policy": "no_argument_creation_or_binding", "capability_only": True},
            },
        ],
    }), encoding="utf-8")
    (policy_dir / "policy_approval_manifest.json").write_text(json.dumps({
        "runtime_enabled": False,
        "selected_non_ambiguous_low_risk_count": 2,
        "candidate_commands": [],
        "planned_commands": [],
    }) + "\n", encoding="utf-8")
    (policy_dir / "compile_status.json").write_text(json.dumps({"runtime_enabled": False}) + "\n", encoding="utf-8")


def _request(user_text: str, tools: list[str], tool_content=None) -> dict:
    messages = [{"role": "user", "content": user_text}]
    if tool_content is not None:
        messages.extend([
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "find", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "c1", "content": json.dumps(tool_content)},
        ])
    return {
        "model": "demo",
        "messages": messages,
        "tools": [{"type": "function", "function": {"name": tool, "parameters": {"type": "object", "properties": {}, "required": []}}} for tool in tools],
    }


def test_runtime_observes_postcondition_gap_predicates() -> None:
    engine = RuleEngine("/tmp/no-rules")

    read = engine._observable_request_predicates(_request("Read report.txt.", ["cat"], {"matches": ["report.txt"]}))
    assert "postcondition_gap_read_content" in read
    assert "prior_tool_outputs_present" in read

    search = engine._observable_request_predicates(_request("Find TODO in the files.", ["grep", "find"], {"files": ["a.txt"]}))
    assert "postcondition_gap_search_or_find" in search

    final = engine._observable_request_predicates(_request("Summarize the prior result.", ["cat"], {"content": "done"}))
    assert "postcondition_gap_read_content" not in final
    assert "postcondition_gap_search_or_find" not in final


def test_postcondition_runtime_adapter_writes_soft_capability_rules(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(builder.dry_check, "evaluate", lambda policy_dir: {"dry_run_policy_boundary_check_passed": True})
    monkeypatch.setattr(builder.activation_audit, "evaluate", lambda policy_dir: {"negative_control_activation_count": 0, "generic_low_risk_match_with_ambiguity_guard_count": 2})
    policy_dir = tmp_path / "policy"
    out_dir = tmp_path / "runtime"
    _write_policy_dir(policy_dir)

    report = builder.evaluate(policy_dir)
    builder.write_outputs(report, out_dir)

    assert report["runtime_adapter_compile_ready"] is True
    assert report["runtime_rule_count"] == 2
    assert report["exact_tool_choice"] is False
    assert report["argument_creation_count"] == 0
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    text = (out_dir / "rule.yaml").read_text(encoding="utf-8")
    assert "candidate_id" not in text
    assert "trace_relative_path" not in text
    rules = yaml.safe_load(text)["rules"]
    assert all(rule["action"]["decision_policy"]["action_candidates"] == [] for rule in rules)


def test_postcondition_runtime_readiness_checks_activation_and_negative_control(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(builder.dry_check, "evaluate", lambda policy_dir: {"dry_run_policy_boundary_check_passed": True})
    monkeypatch.setattr(builder.activation_audit, "evaluate", lambda policy_dir: {"negative_control_activation_count": 0, "generic_low_risk_match_with_ambiguity_guard_count": 2})
    monkeypatch.setattr(readiness.dry_check, "evaluate", lambda policy_dir: {"dry_run_policy_boundary_check_passed": True})
    monkeypatch.setattr(readiness.activation_audit, "evaluate", lambda policy_dir: {"negative_control_activation_count": 0, "approved_record_replay_activation_count": 2, "generic_low_risk_match_with_ambiguity_guard_count": 2})
    policy_dir = tmp_path / "policy"
    runtime_dir = tmp_path / "runtime"
    _write_policy_dir(policy_dir)
    builder.write_outputs(builder.evaluate(policy_dir), runtime_dir)

    report = readiness.evaluate(policy_dir, runtime_dir)

    assert report["postcondition_guided_runtime_smoke_ready"] is True
    assert report["synthetic_read_content_activated"] is True
    assert report["synthetic_search_or_find_activated"] is True
    assert report["synthetic_final_answer_negative_control_activated"] is False
    assert report["synthetic_no_prior_tool_output_negative_control_activated"] is False
    assert report["synthetic_missing_capability_negative_control_activated"] is False
    assert report["does_not_authorize_scorer"] is True


def test_postcondition_runtime_adapter_rejects_runtime_enabled_source_policy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(builder.dry_check, "evaluate", lambda policy_dir: {"dry_run_policy_boundary_check_passed": True})
    monkeypatch.setattr(builder.activation_audit, "evaluate", lambda policy_dir: {"negative_control_activation_count": 0, "generic_low_risk_match_with_ambiguity_guard_count": 2})
    policy_dir = tmp_path / "policy"
    _write_policy_dir(policy_dir)
    data = yaml.safe_load((policy_dir / "policy_unit.yaml").read_text(encoding="utf-8"))
    data["policy_units"][0]["runtime_enabled"] = True
    (policy_dir / "policy_unit.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")

    report = builder.evaluate(policy_dir)

    assert report["runtime_adapter_compile_ready"] is False
    assert any(failure["check"] == "source_unit_runtime_disabled" for failure in report["failures"])
