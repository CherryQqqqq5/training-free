from pathlib import Path
import json

import scripts.diagnose_unmet_postcondition_source_expansion as audit


def _trace(path: Path, *, user: str, output: dict | None, tools: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    messages = [{"role": "user", "content": user}]
    if output is not None:
        messages.append({"type": "function_call_output", "output": json.dumps(output)})
    payload = {
        "request_original": {
            "input": messages,
            "tools": [{"name": name} for name in (tools or ["cat", "grep", "diff"])],
        },
        "validation": {
            "failure_labels": ["(POST_TOOL,POST_TOOL_PROSE_SUMMARY)"],
            "request_predicates": ["prior_tool_outputs_present", "tools_available"],
            "rule_hits": ["rule1"],
        },
    }
    path.write_text(json.dumps(payload) + "\n")


def test_unmet_postcondition_marks_strong_unmet_when_required_evidence_absent(tmp_path: Path) -> None:
    _trace(tmp_path / "run" / "traces" / "case.json", user="Please find the target token", output={"error": "not found"}, tools=["grep"])
    report = audit.evaluate(tmp_path)
    assert report["strong_unmet_candidate_count"] == 1
    row = report["sample_strong_unmet_candidates"][0]
    assert row["required_evidence_type"] == "search_match"
    assert row["typed_satisfaction_label"] == "unmet_strong"
    assert row["postcondition_risk_lane"] == "low_risk_observation"
    assert row["low_risk_observation_candidate"] is True


def test_unmet_postcondition_marks_satisfied_strong_for_matching_evidence(tmp_path: Path) -> None:
    _trace(tmp_path / "run" / "traces" / "case.json", user="Please find the target token", output={"matching_lines": ["target"]}, tools=["grep"])
    report = audit.evaluate(tmp_path)
    assert report["strong_unmet_candidate_count"] == 0
    assert report["typed_satisfaction_distribution"]["satisfied_strong"] == 1


def test_unmet_postcondition_marks_weak_for_related_but_not_exact_evidence(tmp_path: Path) -> None:
    _trace(tmp_path / "run" / "traces" / "case.json", user="Please read the report content", output={"matching_lines": ["report.txt"]}, tools=["cat", "grep"])
    report = audit.evaluate(tmp_path)
    assert report["strong_unmet_candidate_count"] == 0
    assert report["typed_satisfaction_distribution"]["satisfied_weak"] == 1


def test_unmet_postcondition_does_not_emit_scorer_commands(tmp_path: Path) -> None:
    _trace(tmp_path / "run" / "traces" / "case.json", user="Please find the target token", output={"error": "not found"}, tools=["grep"])
    report = audit.evaluate(tmp_path)
    assert report["low_risk_strong_unmet_candidate_count"] == 1
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["does_not_authorize_scorer"] is True
