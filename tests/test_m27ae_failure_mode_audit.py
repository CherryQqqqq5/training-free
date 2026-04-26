from __future__ import annotations

import json
from pathlib import Path

from scripts.diagnose_m27ae_failure_mode_audit import (
    build_ablation_manifest,
    build_ctspc_status,
    evaluate,
)
from scripts.build_m27ae_low_risk_slice_manifest import build_manifest


def _wj(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _wjl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_failure_mode_audit_separates_repair_action_and_trajectory_sources(tmp_path: Path) -> None:
    root = tmp_path / "subset"
    _wj(root / "subset_summary.json", {
        "case_report_trace_mapping": "prompt_user_prefix",
        "case_level_gate_allowed": True,
        "baseline_accuracy": 20.0,
        "candidate_accuracy": 10.0,
        "net_case_gain": -3,
        "case_fixed_count": 1,
        "case_regressed_count": 3,
    })
    _wj(root / "m27x_scorer_proxy_gap.json", {"cases": [
        {"case_id": "traj", "gap_type": "proxy_ok_trajectory_failed"},
        {"case_id": "arg", "gap_type": "proxy_arg_ok_scorer_arg_wrong"},
    ]})
    _wjl(root / "subset_case_report.jsonl", [
        {
            "case_id": "repair",
            "baseline_success": True,
            "candidate_success": False,
            "case_regressed": True,
            "policy_plan_activated": False,
            "repair_kinds": ["coerce_no_tool_text_to_empty"],
        },
        {
            "case_id": "traj",
            "baseline_success": True,
            "candidate_success": False,
            "case_regressed": True,
            "policy_plan_activated": True,
            "selected_next_tool": "mv",
            "recommended_tool_match": True,
            "raw_normalized_arg_match": True,
            "repair_kinds": ["strip_assistant_content_with_tool_calls"],
        },
        {
            "case_id": "arg",
            "baseline_success": True,
            "candidate_success": False,
            "case_regressed": True,
            "policy_plan_activated": True,
            "selected_next_tool": "cat",
            "recommended_tool_match": True,
            "raw_normalized_arg_match": False,
            "repair_kinds": [],
        },
        {
            "case_id": "fixed",
            "baseline_success": False,
            "candidate_success": True,
            "case_fixed": True,
            "policy_plan_activated": True,
            "selected_next_tool": "grep",
            "recommended_tool_match": True,
            "raw_normalized_arg_match": True,
        },
    ])

    report = evaluate(root)
    by_case = {case["case_id"]: case for case in report["cases"]}

    assert report["m27ae_failure_mode_audit_passed"] is True
    assert by_case["repair"]["regression_source"] == "no_tool_repair"
    assert by_case["repair"]["first_divergence_layer"] == "no_tool_repair"
    assert by_case["traj"]["regression_source"] == "trajectory_continuation"
    assert by_case["traj"]["first_divergence_layer"] == "trajectory_continuation"
    assert by_case["arg"]["regression_source"] == "action_policy"
    assert by_case["arg"]["first_divergence_layer"] == "argument_realization"
    assert by_case["fixed"]["regression_source"] == "fixed_signal"
    assert "no_tool_repair" in report["regression_source_distribution"]


def test_ablation_manifest_has_no_scorer_commands() -> None:
    report = build_ablation_manifest(Path("subset"))
    assert report["planned_commands"] == []
    assert report["candidate_commands"] == []
    assert {item["ablation_id"] for item in report["ablation_variants"]} >= {
        "candidate_none",
        "compatibility_repairs_only",
        "action_guidance_only",
        "repair_without_action",
        "action_without_repair",
    }
    assert all(item["contains_executable_scorer_command"] is False for item in report["ablation_variants"])


def test_ctspc_v0_status_freezes_negative_dev_scorer() -> None:
    status = build_ctspc_status(Path("subset"), {"net_case_gain": -3}, {"decision_distribution": {"retain": 0}})
    assert status["ctspc_v0_frozen"] is True
    assert status["scorer_default"] == "off"
    assert status["dev_rerun_authorized"] is False
    assert status["holdout_authorized"] is False
    assert status["retained_rule_count"] == 0


def test_low_risk_slice_scan_excludes_dev_and_holdout_and_emits_no_commands(tmp_path: Path, monkeypatch) -> None:
    dev = tmp_path / "dev"
    hold = tmp_path / "holdout"
    pool = tmp_path / "source_pool"
    source = pool / "multi_turn_base" / "baseline"
    (source / "bfcl" / "score").mkdir(parents=True)
    (source / "bfcl" / "score" / "BFCL_v4_multi_turn_base_score.json").write_text("{}")
    _wj(dev / "paired_subset_manifest.json", {"selected_case_ids": ["dev_case"], "source_run_root": str(tmp_path / "missing")})
    _wj(hold / "holdout_manifest.json", {"selected_case_ids": ["holdout_case"]})

    def fake_scan(root: Path, category: str) -> list[dict]:
        return [
            {"case_id": "dev_case", "schema_local": True, "target_action_tools_present": ["echo"], "candidate_generatable": True},
            {"case_id": "holdout_case", "schema_local": True, "target_action_tools_present": ["grep"], "candidate_generatable": True},
            {"case_id": "fresh_echo", "schema_local": True, "target_action_tools_present": ["echo"], "candidate_generatable": True},
            {"case_id": "fresh_cat", "schema_local": True, "target_action_tools_present": ["cat"], "candidate_generatable": True},
        ]

    monkeypatch.setattr("scripts.build_m27ae_low_risk_slice_manifest.scan_opportunities", fake_scan)
    report = build_manifest(dev, pool, hold)
    all_case_ids = {case["case_id"] for cases in report["slice_cases"].values() for case in cases}

    assert "dev_case" not in all_case_ids
    assert "holdout_case" not in all_case_ids
    assert "fresh_echo" in all_case_ids
    assert report["planned_commands"] == []
    assert report["candidate_commands"] == []
    assert report["m27ae_low_risk_slice_scan_ready"] is True
    assert report["recommended_slice"] in report["slice_counts"]
