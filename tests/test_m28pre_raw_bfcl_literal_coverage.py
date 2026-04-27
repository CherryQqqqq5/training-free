from __future__ import annotations

import json
from pathlib import Path

import scripts.diagnose_m28pre_raw_bfcl_literal_coverage as raw_audit
from scripts.check_m28pre_offline import evaluate as evaluate_m28pre


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _wjl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _candidate(case_id: str, literal: object, required_arg: str = "height") -> dict:
    return {
        "case_id": case_id,
        "category": "simple_python",
        "tool": "calculate_area",
        "required_arg": required_arg,
        "schema_arg_name": required_arg,
        "literal_value": literal,
        "literal_source": "source_result_tool_args",
        "candidate_rules_type": "explicit_required_arg_literal_completion",
        "retention_prior": {
            "rule_family": "explicit_required_arg_literal_completion",
            "retain_eligibility": "diagnostic_only",
            "prior_rejection_reason": "literal_source_not_observable",
        },
        "source_run_root": "source-root",
    }


def _entry(case_id: str, prompt: str, required_arg: str = "height", arg_type: str = "integer") -> dict:
    return {
        "id": case_id,
        "question": [[{"role": "user", "content": prompt}]],
        "function": [{
            "name": "calculate_area",
            "parameters": {
                "type": "dict",
                "properties": {required_arg: {"type": arg_type}},
                "required": [required_arg],
            },
        }],
    }


def _result(literal: object, required_arg: str = "height") -> dict:
    return {"result": [{"calculate_area": json.dumps({required_arg: literal})}]}


def test_raw_prompt_audit_classifies_prompt_source_ambiguous_schema_and_scanner_missed(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "low"
    _wjl(root / "candidate_rules.jsonl", [
        _candidate("prompt_unique", 5),
        _candidate("source_only", 5),
        _candidate("ambiguous", 5),
        _candidate("schema_bad", "five"),
    ])
    entries = {
        "prompt_unique": _entry("prompt_unique", "Set height to 5."),
        "source_only": _entry("source_only", "Set the height from the available source."),
        "ambiguous": _entry("ambiguous", "Try values 5 and 6."),
        "schema_bad": _entry("schema_bad", "Set height to five."),
    }
    results = {case_id: _result(row["literal_value"]) for case_id, row in [("prompt_unique", _candidate("prompt_unique", 5)), ("source_only", _candidate("source_only", 5)), ("ambiguous", _candidate("ambiguous", 5)), ("schema_bad", _candidate("schema_bad", "five"))]}
    monkeypatch.setattr(raw_audit, "_load_dataset_records", lambda category: entries)
    monkeypatch.setattr(raw_audit, "_load_result_records", lambda source_root, category: results)

    report = raw_audit.evaluate(root, tmp_path / "missing_source_manifest.json")
    by_case = {record["case_id"]: record for record in report["records"]}

    assert by_case["prompt_unique"]["retain_prior_candidate"] is True
    assert by_case["prompt_unique"]["failure_reason"] == "scanner_missed"
    assert by_case["source_only"]["failure_reason"] == "source_result_only"
    assert by_case["ambiguous"]["failure_reason"] == "ambiguous"
    assert by_case["schema_bad"]["failure_reason"] == "schema_mismatch"
    assert report["source_result_literals_prompt_anchored_count"] == 3
    assert report["source_result_literals_retain_prior_candidate_count"] == 1
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
    assert report["route_recommendation"] == "fix_current_context_literal_extractor"


def test_raw_prompt_audit_zero_coverage_recommends_next_theory_family(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "low"
    _wjl(root / "candidate_rules.jsonl", [_candidate("source_only", 5)])
    monkeypatch.setattr(raw_audit, "_load_dataset_records", lambda category: {"source_only": _entry("source_only", "Set the height from the available source.")})
    monkeypatch.setattr(raw_audit, "_load_result_records", lambda source_root, category: {"source_only": _result(5)})

    report = raw_audit.evaluate(root, tmp_path / "missing_source_manifest.json")

    assert report["source_result_literals_prompt_anchored_count"] == 0
    assert report["source_result_literals_prompt_coverage_zero"] is True
    assert report["pivot_to_next_theory_family"] == "wrong_arg_key_alias_repair"
    assert report["route_recommendation"] == "pivot_to_next_theory_family=wrong_arg_key_alias_repair"


def test_raw_prompt_coverage_zero_blocks_m28pre_summary(tmp_path: Path) -> None:
    subset = tmp_path / "subset"
    low = tmp_path / "low"
    _wj(subset / "m27ae_ctspc_v0_status.json", {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _wj(subset / "repair_stack_contribution.json", {"repair_stack_split_ready": True})
    _wj(low / "compiler_summary.json", {"compiler_ready": True, "explicit_holdout_ready": True, "ctspc_v0_action_rules_enabled": False, "ctspc_v0_file_path_multi_turn_enabled": False, "repair_stack_default": "disabled", "candidate_rules_type": "explicit_required_arg_literal_completion", "no_next_tool_intervention": True, "exact_tool_choice": False, "retention_prior_required": True, "retain_eligible_candidate_count": 35, "required_explicit_candidate_generatable": 35, "planned_commands": [], "candidate_commands": []})
    _wj(low / "explicit_required_arg_literal_dev20_manifest.json", {"selected_case_ids": [f"d{i}" for i in range(20)], "planned_commands": []})
    _wj(low / "explicit_required_arg_literal_holdout20_manifest.json", {"selected_case_ids": [f"h{i}" for i in range(20)], "planned_commands": []})
    _wj(low / "retention_prior_coverage_audit.json", {"m28pre_retention_prior_coverage_audit_ready": True, "explicit_prior_family_coverage_zero": False, "current_context_anchored_literal_candidate_count": 35, "candidate_commands": [], "planned_commands": []})
    _wj(low / "raw_bfcl_literal_coverage_audit.json", {"m28pre_raw_bfcl_literal_coverage_audit_ready": True, "source_result_literals_prompt_anchored_count": 0, "source_result_literals_prompt_coverage_zero": True, "candidate_commands": [], "planned_commands": []})
    _wj(low / "m28pre_source_result_availability_audit.json", {"source_result_availability_audit_ready": True, "source_result_availability_ready": True, "hard_issue_counts": {}, "issue_counts": {}, "candidate_commands": [], "planned_commands": []})

    report = evaluate_m28pre(subset, low)

    assert report["raw_bfcl_literal_coverage_audit_ready"] is True
    assert "explicit_prior_family_raw_prompt_coverage_zero" in report["blockers"]
    assert report["scorer_authorization_ready"] is False
    assert report["m2_8pre_offline_passed"] is False


def test_raw_prompt_coverage_nonzero_does_not_authorize_without_compiler_candidates(tmp_path: Path) -> None:
    subset = tmp_path / "subset"
    low = tmp_path / "low"
    _wj(subset / "m27ae_ctspc_v0_status.json", {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _wj(subset / "repair_stack_contribution.json", {"repair_stack_split_ready": True})
    _wj(low / "compiler_summary.json", {"compiler_ready": True, "explicit_holdout_ready": False, "ctspc_v0_action_rules_enabled": False, "ctspc_v0_file_path_multi_turn_enabled": False, "repair_stack_default": "disabled", "candidate_rules_type": "explicit_required_arg_literal_completion", "no_next_tool_intervention": True, "exact_tool_choice": False, "retention_prior_required": True, "retain_eligible_candidate_count": 0, "required_explicit_candidate_generatable": 35, "planned_commands": [], "candidate_commands": []})
    _wj(low / "retention_prior_coverage_audit.json", {"m28pre_retention_prior_coverage_audit_ready": True, "explicit_prior_family_coverage_zero": True, "current_context_anchored_literal_candidate_count": 0, "candidate_commands": [], "planned_commands": []})
    _wj(low / "raw_bfcl_literal_coverage_audit.json", {"m28pre_raw_bfcl_literal_coverage_audit_ready": True, "source_result_literals_prompt_anchored_count": 1, "source_result_literals_prompt_coverage_zero": False, "candidate_commands": [], "planned_commands": []})
    _wj(low / "m28pre_source_result_availability_audit.json", {"source_result_availability_audit_ready": True, "source_result_availability_ready": True, "hard_issue_counts": {}, "issue_counts": {}, "candidate_commands": [], "planned_commands": []})

    report = evaluate_m28pre(subset, low)

    assert report["explicit_prior_family_raw_prompt_coverage_zero"] is False
    assert report["source_result_literals_prompt_anchored_count"] == 1
    assert report["scorer_authorization_ready"] is False
