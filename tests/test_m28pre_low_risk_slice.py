from __future__ import annotations

import json
from pathlib import Path

import scripts.build_m28pre_explicit_required_arg_literal as explicit_builder
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


def _source_manifest(path: Path, category: str, source_root: Path) -> None:
    _wj(path, {
        "category_status": [{
            "category": category,
            "source_artifacts_available": True,
            "existing_source_roots": [str(source_root)],
        }],
        "candidate_commands": [],
        "planned_commands": [],
        "source_collection_only": True,
        "no_candidate_rules": True,
    })


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


def test_explicit_required_arg_literal_compiler_builds_dev_holdout_without_commands(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    entries = {}
    results = []
    for i in range(40):
        case_id = f"case_{i}"
        entries[case_id] = {
            "id": case_id,
            "question": [[{"role": "user", "content": f"Calculate the area with base {i} and height {100+i}."}]],
            "function": [{"name": "calculate_area", "parameters": {"type": "dict", "properties": {"base": {"type": "integer"}, "height": {"type": "integer"}}, "required": ["base", "height"]}}],
        }
        results.append({"id": case_id, "result": [{"calculate_area": json.dumps({"base": i})}]})
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: entries if cat == category else {})
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    source_manifest = tmp_path / "source_manifest.json"
    _wj(low, {"slice_cases": {}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _source_manifest(source_manifest, category, source)
    _result(source, category, results)

    report = build(low, status, source_manifest_path=source_manifest)

    assert report["m28pre_low_risk_slice_ready"] is True
    assert report["candidate_generatable_count"] == 40
    assert report["retain_eligible_candidate_count"] == 40
    assert report["theory_prior_explicit_literal_candidate_count"] == 40
    assert report["planned_commands"] == []
    assert report["candidate_commands"] == []
    assert len(set(report["dev_manifest"]["selected_case_ids"]) & set(report["holdout_manifest"]["selected_case_ids"])) == 0
    assert all(rule["literal_source"] == "current_request" for rule in report["candidate_rules"])
    assert all(rule["retention_prior"]["retain_eligibility"] == "demote_candidate" for rule in report["candidate_rules"])
    assert report["retention_prior_distribution"]["demote_candidate"] == 40

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
    assert report["rejected_candidates"][0]["retention_prior"]["retain_eligibility"] == "diagnostic_only"
    assert {row["rejection_reason"] for row in report["rejected_candidates"]} == {"ambiguous_literal", "missing_source_result"}


def test_m28pre_offline_requires_freeze_repair_compiler_holdout_coverage_and_no_commands(tmp_path: Path) -> None:
    subset = tmp_path / "subset"
    low = tmp_path / "low"
    _wj(subset / "m27ae_ctspc_v0_status.json", {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _wj(subset / "repair_stack_contribution.json", {"repair_stack_split_ready": True})
    _wj(low / "compiler_summary.json", {"compiler_ready": True, "explicit_holdout_ready": True, "stratified_holdout_ready": False, "ctspc_v0_action_rules_enabled": False, "ctspc_v0_file_path_multi_turn_enabled": False, "repair_stack_default": "disabled", "candidate_rules_type": "explicit_required_arg_literal_completion", "no_next_tool_intervention": True, "exact_tool_choice": False, "retention_prior_required": True, "retain_eligible_candidate_count": 35, "required_explicit_candidate_generatable": 35, "planned_commands": [], "candidate_commands": []})
    _wj(low / "explicit_required_arg_literal_dev20_manifest.json", {"selected_case_ids": [f"d{i}" for i in range(20)], "planned_commands": []})
    _wj(low / "explicit_required_arg_literal_holdout20_manifest.json", {"selected_case_ids": [f"h{i}" for i in range(20)], "planned_commands": []})
    _wj(low / "retention_prior_coverage_audit.json", {"m28pre_retention_prior_coverage_audit_ready": True, "explicit_prior_family_coverage_zero": False, "current_context_anchored_literal_candidate_count": 35, "candidate_commands": [], "planned_commands": []})
    _wj(low / "raw_bfcl_literal_coverage_audit.json", {"m28pre_raw_bfcl_literal_coverage_audit_ready": True, "source_result_literals_prompt_anchored_count": 35, "source_result_literals_prompt_coverage_zero": False, "candidate_commands": [], "planned_commands": []})
    _wj(low / "m28pre_source_result_availability_audit.json", {"source_result_availability_audit_ready": True, "source_result_availability_ready": True, "hard_issue_counts": {}, "issue_counts": {}, "candidate_commands": [], "planned_commands": []})

    report = evaluate_m28pre(subset, low)

    assert report["m2_8pre_offline_passed"] is True
    _wj(low / "explicit_required_arg_literal_holdout20_manifest.json", {"selected_case_ids": ["d0"], "planned_commands": []})
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
    assert report["stratified_holdout_ready"] is False
    assert report["scorer_authorization_ready"] is False
    assert report["stratified_retention_prior_distribution"]["diagnostic_only"] == 45
    assert report["planned_commands"] == []
    assert report["candidate_commands"] == []
    assert set(report["stratified_counts"]) == set(slice_cases)
    assert "stratified_without_complete_theory_priors_not_authorized" in report["blockers"]

def test_m28pre_safeguards_fail_when_ctspc_or_repair_stack_enabled(tmp_path: Path) -> None:
    subset = tmp_path / "subset"
    low = tmp_path / "low"
    _wj(subset / "m27ae_ctspc_v0_status.json", {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _wj(subset / "repair_stack_contribution.json", {"repair_stack_split_ready": True})
    _wj(low / "compiler_summary.json", {"compiler_ready": True, "explicit_holdout_ready": True, "ctspc_v0_action_rules_enabled": True, "ctspc_v0_file_path_multi_turn_enabled": False, "repair_stack_default": "enabled", "candidate_rules_type": "explicit_required_arg_literal_completion", "no_next_tool_intervention": True, "exact_tool_choice": False, "retention_prior_required": True, "retain_eligible_candidate_count": 35, "required_explicit_candidate_generatable": 35, "planned_commands": [], "candidate_commands": []})
    _wj(low / "explicit_required_arg_literal_dev20_manifest.json", {"selected_case_ids": [f"d{i}" for i in range(20)], "planned_commands": []})
    _wj(low / "explicit_required_arg_literal_holdout20_manifest.json", {"selected_case_ids": [f"h{i}" for i in range(20)], "planned_commands": []})
    _wj(low / "retention_prior_coverage_audit.json", {"m28pre_retention_prior_coverage_audit_ready": True, "explicit_prior_family_coverage_zero": False, "current_context_anchored_literal_candidate_count": 35, "candidate_commands": [], "planned_commands": []})
    _wj(low / "raw_bfcl_literal_coverage_audit.json", {"m28pre_raw_bfcl_literal_coverage_audit_ready": True, "source_result_literals_prompt_anchored_count": 35, "source_result_literals_prompt_coverage_zero": False, "candidate_commands": [], "planned_commands": []})
    _wj(low / "m28pre_source_result_availability_audit.json", {"source_result_availability_audit_ready": True, "source_result_availability_ready": True, "hard_issue_counts": {}, "issue_counts": {}, "candidate_commands": [], "planned_commands": []})

    report = evaluate_m28pre(subset, low)

    assert report["runtime_manifest_safeguards_passed"] is False
    assert report["scorer_authorization_ready"] is False


def test_explicit_compiler_reads_non_multi_turn_result_layout(tmp_path: Path) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": {"explicit_required_arg_literal": [{
        "case_id": "simple_python_0",
        "category": category,
        "source_run_root": str(source),
        "schema_local": True,
        "target_action_tools_present": ["echo"],
        "low_risk_slices": ["explicit_required_arg_literal"],
    }]}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    path = source / "bfcl" / "result" / "model" / "simple" / f"BFCL_v4_{category}_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"id": "simple_python_0", "result": [[[{"echo": json.dumps({"content": "literal"})}]]]}) + "\n", encoding="utf-8")

    report = build(low, status)

    assert report["candidate_generatable_count"] == 1
    assert report["candidate_rules"][0]["literal_value"] == "literal"


def test_m28pre_summary_reports_source_pool_expansion_required_when_holdout_missing(tmp_path: Path) -> None:
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

    assert report["source_pool_expansion_required"] is True
    assert report["explicit_source_pool_expansion_required"] is True
    assert report["required_explicit_total"] == 40
    assert report["required_explicit_candidate_generatable"] == 35


def test_legacy_prompt_anchored_folder_literal_becomes_demote_candidate(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "multi_turn_miss_func"
    case_id = "multi_turn_miss_func_7"
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": {"explicit_required_arg_literal": [{
        "case_id": case_id,
        "category": category,
        "source_run_root": str(source),
        "schema_local": True,
        "target_action_tools_present": ["cd"],
        "low_risk_slices": ["explicit_required_arg_literal"],
    }]}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _result(source, category, [{"id": case_id, "result": [[[{"cd": json.dumps({"folder": "academic_venture"})}]]]}])
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: {
        case_id: {
            "id": case_id,
            "question": [[{"role": "user", "content": "Please cd into the academic_venture directory."}]],
            "function": [{"name": "cd", "parameters": {"type": "dict", "properties": {"folder": {"type": "string"}}, "required": ["folder"]}}],
        }
    } if cat == category else {})

    report = build(low, status)

    assert report["retain_eligible_candidate_count"] == 1
    rule = report["candidate_rules"][0]
    assert rule["literal_value"] == "academic_venture"
    assert rule["literal_source"] == "current_request"
    assert rule["retention_prior"]["retain_eligibility"] == "demote_candidate"
    assert report["disambiguated_current_context_candidate_count"] == 1
    assert report["source_result_only_diagnostic_count"] == 0


def test_legacy_file_literal_disambiguates_among_multiple_prompt_literals(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "multi_turn_miss_func"
    case_id = "multi_turn_miss_func_8"
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": {"explicit_required_arg_literal": [{
        "case_id": case_id,
        "category": category,
        "source_run_root": str(source),
        "schema_local": True,
        "target_action_tools_present": ["grep"],
        "low_risk_slices": ["explicit_required_arg_literal"],
    }]}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _result(source, category, [{"id": case_id, "result": [[[{"grep": json.dumps({"file_name": "experiment_log.txt", "pattern": "Anomaly"})}]]]}])
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: {
        case_id: {
            "id": case_id,
            "question": [[{"role": "user", "content": "Search experiment_log.txt for 'Anomaly' and compare it with previous_study_log.txt."}]],
            "function": [{"name": "grep", "parameters": {"type": "dict", "properties": {"file_name": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["file_name", "pattern"]}}],
        }
    } if cat == category else {})

    report = build(low, status)

    assert report["retain_eligible_candidate_count"] == 1
    rule = report["candidate_rules"][0]
    assert rule["literal_value"] == "experiment_log.txt"
    assert rule["disambiguation_cue"] == "file_name_exact_prompt_literal"
    assert rule["retention_prior"]["retain_eligibility"] == "demote_candidate"


def test_source_result_only_literal_remains_diagnostic(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "multi_turn_miss_func"
    case_id = "source_only"
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": {"explicit_required_arg_literal": [{
        "case_id": case_id,
        "category": category,
        "source_run_root": str(source),
        "schema_local": True,
        "target_action_tools_present": ["cat"],
        "low_risk_slices": ["explicit_required_arg_literal"],
    }]}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _result(source, category, [{"id": case_id, "result": [[[{"cat": json.dumps({"file_name": "hidden.txt"})}]]]}])
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: {
        case_id: {
            "id": case_id,
            "question": [[{"role": "user", "content": "Show the relevant hidden file from the source result."}]],
            "function": [{"name": "cat", "parameters": {"type": "dict", "properties": {"file_name": {"type": "string"}}, "required": ["file_name"]}}],
        }
    } if cat == category else {})

    report = build(low, status)

    assert report["retain_eligible_candidate_count"] == 0
    rule = report["candidate_rules"][0]
    assert rule["literal_source"] == "source_result_tool_args"
    assert rule["retention_prior"]["retain_eligibility"] == "diagnostic_only"
    assert report["source_result_only_diagnostic_count"] == 1


def test_literal_disambiguation_report_is_written(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "multi_turn_miss_func"
    case_id = "multi_turn_miss_func_7"
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    out = tmp_path / "out"
    _wj(low, {"slice_cases": {"explicit_required_arg_literal": [{
        "case_id": case_id,
        "category": category,
        "source_run_root": str(source),
        "schema_local": True,
        "target_action_tools_present": ["cd"],
        "low_risk_slices": ["explicit_required_arg_literal"],
    }]}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _result(source, category, [{"id": case_id, "result": [[[{"cd": json.dumps({"folder": "academic_venture"})}]]]}])
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: {
        case_id: {
            "id": case_id,
            "question": [[{"role": "user", "content": "Please cd into the academic_venture directory."}]],
            "function": [{"name": "cd", "parameters": {"type": "dict", "properties": {"folder": {"type": "string"}}, "required": ["folder"]}}],
        }
    } if cat == category else {})

    report = build(low, status)
    explicit_builder.write_outputs(report, out)
    disamb = json.loads((out / "m28pre_literal_disambiguation_report.json").read_text())

    assert disamb["candidate_commands"] == []
    assert disamb["planned_commands"] == []
    assert disamb["records"][0]["selected_literal"] == "academic_venture"
    assert disamb["records"][0]["retain_prior_candidate"] is True


def _area_entry(case_id: str, prompt: str = "Calculate area with base 3 and height 7.") -> dict:
    return {
        "id": case_id,
        "question": [[{"role": "user", "content": prompt}]],
        "function": [{
            "name": "calculate_area",
            "parameters": {
                "type": "dict",
                "properties": {"base": {"type": "integer"}, "height": {"type": "integer"}},
                "required": ["base", "height"],
            },
        }],
    }


def test_source_result_availability_audit_detects_unrecognized_result_layout(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    case_id = "case_layout"
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: {case_id: _area_entry(case_id)} if cat == category else {})
    source_manifest = tmp_path / "source_manifest.json"
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": {}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _source_manifest(source_manifest, category, source)
    path = source / "bfcl" / "result" / "model" / "simple" / f"BFCL_v4_{category}_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"unexpected": "shape"}) + "\n", encoding="utf-8")

    report = build(low, status, source_manifest_path=source_manifest)
    audit = report["source_result_availability_audit"]

    assert audit["source_result_availability_audit_ready"] is True
    assert audit["source_result_availability_ready"] is False
    assert audit["hard_issue_counts"]["result_layout_unrecognized"] == 1
    assert audit["issue_counts"]["result_layout_unrecognized"] == 1


def test_source_result_availability_audit_classifies_case_id_no_tool_complete_and_parallel(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    entries = {
        "case_missing": _area_entry("case_missing"),
        "case_no_tool": _area_entry("case_no_tool"),
        "case_complete": _area_entry("case_complete"),
        "case_parallel": _area_entry("case_parallel"),
    }
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: entries if cat == category else {})
    source_manifest = tmp_path / "source_manifest.json"
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": {}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _source_manifest(source_manifest, category, source)
    path = source / "bfcl" / "result" / "model" / "simple" / f"BFCL_v4_{category}_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"id": "unmatched_case", "result": [{"calculate_area": json.dumps({"base": 3})}]},
        {"id": "case_no_tool", "result": "no tool call"},
        {"id": "case_complete", "result": [{"calculate_area": json.dumps({"base": 3, "height": 7})}]},
        {"id": "case_parallel", "result": [{"calculate_area": json.dumps({"base": 3})}, {"calculate_area": json.dumps({"base": 4})}]},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    report = build(low, status, source_manifest_path=source_manifest)
    counts = report["source_result_availability_audit"]["issue_counts"]

    assert counts["source_result_case_not_collected"] == 1
    assert counts["baseline_no_tool_call"] == 1
    assert counts["emitted_args_complete"] == 1
    assert counts["parallel_call_mapping_not_unique"] == 1


def test_prior_scan_category_coverage_reports_accepts_and_rejects(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    entries = {
        "case_ok": _area_entry("case_ok", "Calculate area with base 3 and height 7."),
        "case_parallel": _area_entry("case_parallel", "Calculate area with base 3 and height 7."),
    }
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: entries if cat == category else {})
    source_manifest = tmp_path / "source_manifest.json"
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    _wj(low, {"slice_cases": {}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _source_manifest(source_manifest, category, source)
    _result(source, category, [
        {"id": "case_ok", "result": [{"calculate_area": json.dumps({"base": 3})}]},
        {"id": "case_parallel", "result": [{"calculate_area": json.dumps({"base": 3})}, {"calculate_area": json.dumps({"base": 4})}]},
    ])

    report = build(low, status, source_manifest_path=source_manifest)
    coverage = report["prior_scan_category_coverage"][category]

    assert coverage["accepted_count"] == 1
    assert coverage["rejected_count"] == 1
    assert coverage["accepted_by_tool_required_arg"] == {"calculate_area::height": 1}
    assert coverage["rejection_reason_counts"] == {"parallel_call_mapping_not_unique": 1}


def _alias_entry(case_id: str, tool: str = "cat", canonical: str = "file_name") -> dict:
    return {
        "id": case_id,
        "question": [[{"role": "user", "content": "Use the emitted tool arguments exactly as provided."}]],
        "function": [{
            "name": tool,
            "parameters": {
                "type": "dict",
                "properties": {canonical: {"type": "string"}},
                "required": [canonical],
            },
        }],
    }


def test_wrong_arg_key_alias_compiler_builds_demote_candidates(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    entries = {
        "file_case": _alias_entry("file_case", "cat", "file_name"),
        "dir_case": _alias_entry("dir_case", "cd", "dir_name"),
        "dest_case": _alias_entry("dest_case", "mv", "destination"),
    }
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: entries if cat == category else {})
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    source_manifest = tmp_path / "source_manifest.json"
    _wj(low, {"slice_cases": {}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _source_manifest(source_manifest, category, source)
    _result(source, category, [
        {"id": "file_case", "result": [{"cat": json.dumps({"filename": "report.txt"})}]},
        {"id": "dir_case", "result": [{"cd": json.dumps({"dir": "workspace"})}]},
        {"id": "dest_case", "result": [{"mv": json.dumps({"dest": "archive.txt"})}]},
    ])

    report = build(low, status, source_manifest_path=source_manifest)

    assert report["wrong_arg_key_alias_demote_candidate_count"] == 3
    mappings = {(row["original_arg_key"], row["canonical_arg_key"]) for row in report["wrong_arg_key_alias_candidate_rules"]}
    assert ("filename", "file_name") in mappings
    assert ("dir", "dir_name") in mappings
    assert ("dest", "destination") in mappings
    assert all(row["value_mutation"] is False for row in report["wrong_arg_key_alias_candidate_rules"])
    assert all(row["retention_prior"]["retain_eligibility"] == "demote_candidate" for row in report["wrong_arg_key_alias_candidate_rules"])


def test_wrong_arg_key_alias_rejects_ambiguous_present_or_nonunique_calls(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    entries = {
        "present": _alias_entry("present", "cat", "file_name"),
        "parallel": _alias_entry("parallel", "cat", "file_name"),
    }
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: entries if cat == category else {})
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    source_manifest = tmp_path / "source_manifest.json"
    _wj(low, {"slice_cases": {}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _source_manifest(source_manifest, category, source)
    _result(source, category, [
        {"id": "present", "result": [{"cat": json.dumps({"filename": "report.txt", "file_name": "report.txt"})}]},
        {"id": "parallel", "result": [{"cat": json.dumps({"filename": "a.txt"})}, {"cat": json.dumps({"filename": "b.txt"})}]},
    ])

    report = build(low, status, source_manifest_path=source_manifest)
    reasons = {row["rejection_reason"] for row in report["wrong_arg_key_alias_rejected_candidates"]}

    assert report["wrong_arg_key_alias_demote_candidate_count"] == 0
    assert "canonical_key_already_present" in reasons
    assert "parallel_call_mapping_not_unique" in reasons


def test_combined_theory_prior_pool_can_authorize_only_explicit_and_alias(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "source"
    category = "simple_python"
    entries = {}
    results = []
    for i in range(35):
        case_id = f"alias_{i}"
        entries[case_id] = _alias_entry(case_id, "cat", "file_name")
        results.append({"id": case_id, "result": [{"cat": json.dumps({"filename": f"report_{i}.txt"})}]})
    monkeypatch.setattr(explicit_builder, "_load_dataset_records", lambda cat: entries if cat == category else {})
    low = tmp_path / "low.json"
    status = tmp_path / "status.json"
    source_manifest = tmp_path / "source_manifest.json"
    _wj(low, {"slice_cases": {}})
    _wj(status, {"ctspc_v0_frozen": True, "scorer_default": "off", "retain": 0, "dev_rerun_authorized": False, "holdout_authorized": False})
    _source_manifest(source_manifest, category, source)
    _result(source, category, results)

    report = build(low, status, source_manifest_path=source_manifest)

    assert report["combined_retain_eligible_candidate_count"] == 35
    assert report["combined_theory_prior_holdout_ready"] is False
    assert report["wrong_arg_key_alias_demote_candidate_count"] == 35
    assert set(report["combined_dev_manifest"]["authorized_theory_prior_families"]) == {"wrong_arg_key_alias_repair"}
    assert report["planned_commands"] == []
    assert report["candidate_commands"] == []
