from __future__ import annotations

import json
from pathlib import Path

from scripts.build_m28pre_explicit_required_arg_literal import build
from scripts.check_m28pre_offline import evaluate as evaluate_m28pre
from scripts.diagnose_repair_stack_contribution import evaluate as evaluate_repair_stack


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _wjl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _result(root: Path, category: str, rows: list[dict]) -> None:
    path = root / "bfcl" / "result" / "model" / "multi_turn" / f"BFCL_v4_{category}_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_repair_stack_splits_repair_only_action_and_mixed_sources(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _wj(root / "subset_summary.json", {"net_case_gain": -3})
    _wj(root / "m27ae_failure_mode_audit.json", {"cases": [
        {"case_id": "repair", "regression_source": "no_tool_repair"},
        {"case_id": "action", "regression_source": "action_policy"},
        {"case_id": "fixed", "regression_source": "fixed_signal"},
    ]})
    _wjl(root / "subset_case_report.jsonl", [
        {"case_id": "repair", "case_regressed": True, "repair_kinds": ["coerce_no_tool_text_to_empty"], "policy_plan_activated": False},
        {"case_id": "action", "case_regressed": True, "repair_kinds": ["resolve_contextual_string_arg"], "policy_plan_activated": True},
        {"case_id": "fixed", "case_fixed": True, "repair_kinds": ["resolve_contextual_string_arg"], "policy_plan_activated": True},
    ])

    report = evaluate_repair_stack(root)

    assert report["repair_stack_split_ready"] is True
    assert report["repairs"]["coerce_no_tool_text_to_empty"]["decision"] == "disable"
    assert report["repairs"]["coerce_no_tool_text_to_empty"]["interaction_with_repair_policy"] == 1
    assert report["repairs"]["resolve_contextual_string_arg"]["interaction_with_action_policy"] == 1


def test_explicit_required_arg_literal_compiler_builds_dev_holdout_without_commands(tmp_path: Path) -> None:
    source = tmp_path / "source"
    category = "multi_turn_base"
    records = []
    results = []
    for i in range(40):
        case_id = f"case_{i}"
        records.append({
            "case_id": case_id,
            "category": category,
            "source_run_root": str(source),
            "schema_local": True,
            "target_action_tools_present": ["echo"],
            "low_risk_slices": ["explicit_required_arg_literal"],
        })
        results.append({"id": case_id, "result": [[[{"echo": json.dumps({"content": f"literal-{i}"})}]]]})
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": {"explicit_required_arg_literal": records}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _result(source, category, results)

    report = build(low, status)

    assert report["m28pre_low_risk_slice_ready"] is True
    assert report["candidate_generatable_count"] == 40
    assert report["ambiguous_literal_count"] == 0
    assert report["planned_commands"] == []
    assert report["candidate_commands"] == []
    assert len(set(report["dev_manifest"]["selected_case_ids"]) & set(report["holdout_manifest"]["selected_case_ids"])) == 0
    assert all(rule["no_next_tool_intervention"] for rule in report["candidate_rules"])
    assert all(rule["exact_tool_choice"] is False for rule in report["candidate_rules"])


def test_explicit_literal_compiler_rejects_ambiguous_or_missing_literals(tmp_path: Path) -> None:
    source = tmp_path / "source"
    category = "multi_turn_base"
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": {"explicit_required_arg_literal": [
        {"case_id": "bad", "category": category, "source_run_root": str(source), "schema_local": True, "target_action_tools_present": ["echo"], "low_risk_slices": ["explicit_required_arg_literal"]},
        {"case_id": "missing", "category": category, "source_run_root": str(source), "schema_local": True, "target_action_tools_present": ["echo"], "low_risk_slices": ["explicit_required_arg_literal"]},
    ]}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _result(source, category, [{"id": "bad", "result": [[[{"echo": json.dumps({"content": "x" * 260})}]]]}])

    report = build(low, status)

    assert report["candidate_generatable_count"] == 0
    assert report["ambiguous_literal_count"] == 1
    assert {row["rejection_reason"] for row in report["rejected_candidates"]} == {"ambiguous_literal", "missing_source_result"}


def test_m28pre_offline_requires_freeze_repair_compiler_holdout_and_no_commands(tmp_path: Path) -> None:
    subset = tmp_path / "subset"
    low = tmp_path / "low"
    _wj(subset / "m27ae_ctspc_v0_status.json", {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _wj(subset / "repair_stack_contribution.json", {"repair_stack_split_ready": True})
    _wj(low / "compiler_summary.json", {"compiler_ready": True, "explicit_holdout_ready": True, "stratified_holdout_ready": False, "ctspc_v0_action_rules_enabled": False, "ctspc_v0_file_path_multi_turn_enabled": False, "repair_stack_default": "disabled", "candidate_rules_type": "explicit_required_arg_literal_completion", "no_next_tool_intervention": True, "exact_tool_choice": False, "planned_commands": [], "candidate_commands": []})
    _wj(low / "explicit_required_arg_literal_dev20_manifest.json", {"selected_case_ids": ["a"], "planned_commands": []})
    _wj(low / "explicit_required_arg_literal_holdout20_manifest.json", {"selected_case_ids": ["b"], "planned_commands": []})

    report = evaluate_m28pre(subset, low)

    assert report["m2_8pre_offline_passed"] is True
    _wj(low / "explicit_required_arg_literal_holdout20_manifest.json", {"selected_case_ids": ["a"], "planned_commands": []})
    report = evaluate_m28pre(subset, low)
    assert report["dev_holdout_disjoint"] is False
    assert report["m2_8pre_offline_passed"] is False



def test_explicit_only_below_40_keeps_scorer_blocked_even_when_compiler_ready(tmp_path: Path) -> None:
    source = tmp_path / "source"
    category = "multi_turn_base"
    records = []
    results = []
    for i in range(28):
        case_id = f"case_{i}"
        records.append({"case_id": case_id, "category": category, "source_run_root": str(source), "schema_local": True, "target_action_tools_present": ["echo"], "low_risk_slices": ["explicit_required_arg_literal"]})
        if i < 25:
            results.append({"id": case_id, "result": [[[{"echo": json.dumps({"content": f"literal-{i}"})}]]]})
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": {"explicit_required_arg_literal": records}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _result(source, category, results)

    report = build(low, status)

    assert report["compiler_ready"] is True
    assert report["explicit_holdout_ready"] is False
    assert report["scorer_authorization_ready"] is False
    assert "explicit_total_below_40" in report["blockers"]


def test_stratified_fallback_preserves_slice_labels_without_commands(tmp_path: Path) -> None:
    source = tmp_path / "source"
    category = "multi_turn_base"
    slice_cases = {"explicit_required_arg_literal": [], "wrong_arg_key_alias_repair": [], "deterministic_schema_local_non_live_repair": []}
    results = []
    for i in range(45):
        case_id = f"case_{i}"
        slice_name = list(slice_cases)[i % 3]
        row = {"case_id": case_id, "category": category, "source_run_root": str(source), "schema_local": True, "target_action_tools_present": ["echo"], "low_risk_slices": [slice_name]}
        slice_cases[slice_name].append(row)
        results.append({"id": case_id, "result": [[[{"echo": json.dumps({"content": f"literal-{i}"})}]]]})
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": slice_cases})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _result(source, category, results)

    report = build(low, status)

    assert report["explicit_holdout_ready"] is False
    assert report["stratified_holdout_ready"] is True
    assert report["scorer_authorization_ready"] is True
    assert report["planned_commands"] == []
    assert report["candidate_commands"] == []
    assert set(report["stratified_counts"]) == set(slice_cases)


def test_m28pre_safeguards_fail_when_ctspc_or_repair_stack_enabled(tmp_path: Path) -> None:
    subset = tmp_path / "subset"
    low = tmp_path / "low"
    _wj(subset / "m27ae_ctspc_v0_status.json", {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _wj(subset / "repair_stack_contribution.json", {"repair_stack_split_ready": True})
    _wj(low / "compiler_summary.json", {"compiler_ready": True, "explicit_holdout_ready": True, "ctspc_v0_action_rules_enabled": True, "ctspc_v0_file_path_multi_turn_enabled": False, "repair_stack_default": "enabled", "candidate_rules_type": "explicit_required_arg_literal_completion", "no_next_tool_intervention": True, "exact_tool_choice": False, "planned_commands": [], "candidate_commands": []})
    _wj(low / "explicit_required_arg_literal_dev20_manifest.json", {"selected_case_ids": ["a"], "planned_commands": []})
    _wj(low / "explicit_required_arg_literal_holdout20_manifest.json", {"selected_case_ids": ["b"], "planned_commands": []})

    report = evaluate_m28pre(subset, low)

    assert report["runtime_manifest_safeguards_passed"] is False
    assert report["scorer_authorization_ready"] is False
