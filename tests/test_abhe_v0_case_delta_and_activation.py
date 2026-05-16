from __future__ import annotations

import json
from pathlib import Path

from scripts.analyze_abhe_v0_bfcl_case_deltas import build_analysis
from scripts.check_abhe_v0_bfcl_case_delta_analysis import validate_analysis
from grc.runtime import proxy


def test_case_delta_analysis_is_compact_and_marks_scaled_category_delta() -> None:
    analysis = build_analysis()
    assert validate_analysis(analysis) == []
    assert analysis["selected_compact_case_count"] == 20
    assert analysis["unique_bfcl_scorer_unit_count"] == 7
    assert analysis["strict_per_compact_case_paired_available"] is False
    assert analysis["aggregate_feedback_fixed_count_is_scaled_category_delta"] is True
    assert analysis["raw_material_absent"] is True
    assert analysis["performance_evidence"] is False


def test_proxy_entry_specific_activation_by_entry_env(monkeypatch, tmp_path: Path) -> None:
    adapter = {
        "artifact_kind": "abhe_v0_runtime_candidate_adapter",
        "adapter_ready": True,
        "candidate_jsonl_generated": False,
        "candidate_rule_generated": False,
        "candidate_yaml_generated": False,
        "runtime_projection": [
            {"entry_id": "state_tracking_v0", "candidate_type": "state_summary_injection", "activation_categories": ["multi_turn_base"]},
            {"entry_id": "hallucination_abstain_v0", "candidate_type": "evidence_boundary_verifier", "activation_categories": ["irrelevance"]},
        ],
    }
    adapter_path = tmp_path / "adapter.json"
    adapter_path.write_text(json.dumps(adapter), encoding="utf-8")
    monkeypatch.setenv("ABHE_V0_RUNTIME_CANDIDATE_ADAPTER", str(adapter_path))
    monkeypatch.setenv("ABHE_V0_RUNTIME_ACTIVATION_ENTRY", "state_tracking_v0")
    patched, patches = proxy._apply_abhe_v0_adapter_guidance({"messages": [{"role": "user", "content": "x"}]})
    assert patches == ["abhe_v0_runtime_candidate_adapter_guidance:state_tracking_v0"]
    guidance = patched["messages"][0]["content"]
    assert "multi-turn state carryover" in guidance
    assert "answerability-boundary" not in guidance


def test_proxy_entry_specific_activation_by_category_env(monkeypatch, tmp_path: Path) -> None:
    adapter = {
        "artifact_kind": "abhe_v0_runtime_candidate_adapter",
        "adapter_ready": True,
        "candidate_jsonl_generated": False,
        "candidate_rule_generated": False,
        "candidate_yaml_generated": False,
        "runtime_projection": [
            {"entry_id": "state_tracking_v0", "candidate_type": "state_summary_injection", "activation_categories": ["multi_turn_base"]},
            {"entry_id": "hallucination_abstain_v0", "candidate_type": "evidence_boundary_verifier", "activation_categories": ["irrelevance"]},
        ],
    }
    adapter_path = tmp_path / "adapter.json"
    adapter_path.write_text(json.dumps(adapter), encoding="utf-8")
    monkeypatch.setenv("ABHE_V0_RUNTIME_CANDIDATE_ADAPTER", str(adapter_path))
    monkeypatch.delenv("ABHE_V0_RUNTIME_ACTIVATION_ENTRY", raising=False)
    monkeypatch.setenv("ABHE_V0_RUNTIME_ACTIVATION_CATEGORIES", "irrelevance")
    patched, patches = proxy._apply_abhe_v0_adapter_guidance({"messages": [{"role": "user", "content": "x"}]})
    assert patches == ["abhe_v0_runtime_candidate_adapter_guidance:hallucination_abstain_v0"]
    guidance = patched["messages"][0]["content"]
    assert "answerability-boundary" in guidance
    assert "multi-turn state carryover" not in guidance
