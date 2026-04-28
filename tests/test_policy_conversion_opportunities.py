from __future__ import annotations

import json
from pathlib import Path

import scripts.diagnose_policy_conversion_opportunities as audit


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


def test_postcondition_policy_candidate_from_rule_hit_trace(tmp_path: Path) -> None:
    _trace(
        tmp_path / "soft_target" / "traces" / "one.json",
        user="Please create a new file named report.txt.",
        labels=["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
        predicates=["prior_tool_outputs_present", "tools_available", "prior_explicit_literals_present"],
        rule_hits=["rule1"],
        tools=["touch", "cat"],
    )

    report = audit.evaluate(tmp_path)

    assert report["policy_candidate_count"] == 1
    candidate = report["sample_candidates"][0]
    assert candidate["policy_family"] == "postcondition_guided_trajectory_policy"
    assert candidate["postcondition_gap"] == "create_file"
    assert candidate["recommended_tools"] == ["touch"]
    assert candidate["exact_tool_choice"] is False
    assert candidate["target_or_scorer_field_dependency"] is False
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []


def test_policy_opportunity_rejects_no_rule_hit_or_no_prior_observation(tmp_path: Path) -> None:
    _trace(
        tmp_path / "soft_target" / "traces" / "no_rule.json",
        user="Please read report.txt.",
        labels=["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
        predicates=["prior_tool_outputs_present", "tools_available"],
        rule_hits=[],
        tools=["cat"],
    )
    _trace(
        tmp_path / "soft_target" / "traces" / "no_prior.json",
        user="Please read report.txt.",
        labels=["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
        predicates=["tools_available"],
        rule_hits=["rule1"],
        tools=["cat"],
        include_tool_output=False,
    )

    report = audit.evaluate(tmp_path)

    assert report["policy_candidate_count"] == 0
    assert report["rejection_reason_counts"]["no_rule_hit"] == 1
    assert report["rejection_reason_counts"]["no_prior_observation_for_postcondition_policy"] == 1


def test_policy_opportunity_requires_schema_local_recommended_tool(tmp_path: Path) -> None:
    _trace(
        tmp_path / "soft_target" / "traces" / "missing_tool.json",
        user="Please search for budget analysis.",
        labels=["(POST_TOOL,ACTIONABLE_NO_TOOL_DECISION)"],
        predicates=["prior_tool_outputs_present", "tools_available"],
        rule_hits=["rule1"],
        tools=["cat"],
    )

    report = audit.evaluate(tmp_path)

    assert report["policy_candidate_count"] == 0
    assert report["rejection_reason_counts"]["no_schema_local_recommended_tool"] == 1


def test_policy_opportunity_rejects_already_satisfied_postcondition(tmp_path: Path) -> None:
    _trace(
        tmp_path / "soft_target" / "traces" / "already.json",
        user="Please search for budget analysis.",
        labels=["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
        predicates=["prior_tool_outputs_present", "tools_available"],
        rule_hits=["rule1"],
        tools=["grep", "find"],
    )
    payload = json.loads((tmp_path / "soft_target" / "traces" / "already.json").read_text())
    payload["request_original"]["input"][-1]["output"] = json.dumps({"matches": ["./budget.txt"]})
    (tmp_path / "soft_target" / "traces" / "already.json").write_text(json.dumps(payload) + "\n")

    report = audit.evaluate(tmp_path)

    assert report["policy_candidate_count"] == 0
    assert report["rejection_reason_counts"]["postcondition_already_satisfied"] == 1
    rejected = report["sample_rejections"][0]
    assert rejected["postcondition_already_satisfied"] is True
    assert rejected["satisfied_witness_keys"] == ["matches"]



def test_policy_opportunity_rejects_terminal_evidence_witness_aliases(tmp_path: Path) -> None:
    examples = [
        ("diff.json", "Compare the content difference of both files.", ["diff"], {"diff_lines": "- a\n+ b"}),
        ("grep.json", "Use grep to find the function name.", ["grep"], {"matching_lines": ["def deploy(): pass"]}),
        ("tail.json", "Display the last line of the file.", ["cat", "tail"], {"last_lines": "done"}),
        ("sort.json", "Show the sorted contents of the report.", ["cat", "sort"], {"sorted_content": "a b c"}),
    ]
    for filename, user, tools, output in examples:
        _trace(
            tmp_path / "soft_target" / "traces" / filename,
            user=user,
            labels=["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
            predicates=["prior_tool_outputs_present", "tools_available"],
            rule_hits=["rule1"],
            tools=tools,
        )
        payload = json.loads((tmp_path / "soft_target" / "traces" / filename).read_text())
        payload["request_original"]["input"][-1]["output"] = json.dumps(output)
        (tmp_path / "soft_target" / "traces" / filename).write_text(json.dumps(payload) + "\n")

    report = audit.evaluate(tmp_path)

    assert report["policy_candidate_count"] == 0
    assert report["rejection_reason_counts"]["postcondition_already_satisfied"] == 4


def test_policy_opportunity_rejects_directory_listing_as_satisfied_for_list_files_request(tmp_path: Path) -> None:
    _trace(
        tmp_path / "soft_target" / "traces" / "list_files.json",
        user="Could you show me the list of files in tmp directory?",
        labels=["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
        predicates=["prior_tool_outputs_present", "tools_available"],
        rule_hits=["rule1"],
        tools=["cat", "ls"],
    )
    payload = json.loads((tmp_path / "soft_target" / "traces" / "list_files.json").read_text())
    payload["request_original"]["input"][-1]["output"] = json.dumps({"current_directory_content": ["report.txt"]})
    (tmp_path / "soft_target" / "traces" / "list_files.json").write_text(json.dumps(payload) + "\n")

    report = audit.evaluate(tmp_path)

    assert report["policy_candidate_count"] == 0
    assert report["rejection_reason_counts"]["postcondition_already_satisfied"] == 1
    assert report["sample_rejections"][0]["satisfied_witness_keys"] == ["current_directory_content"]
