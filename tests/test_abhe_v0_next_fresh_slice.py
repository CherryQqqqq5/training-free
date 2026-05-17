from __future__ import annotations
import json
from pathlib import Path

from scripts.build_abhe_v0_next_fresh_slice import build as build_next_slice
from scripts.build_abhe_v0_next_candidate_specs import build as build_next_specs

ROOT = Path("outputs/artifacts/stage1_bfcl_acceptance")


def test_next_fresh_slice_has_no_source_or_old_slice_overlap() -> None:
    payload = build_next_slice()
    assert payload["plan"]["blockers"] == []
    proof = payload["proof"]
    assert proof["overlap_count"] == 0
    assert proof["archive_source_overlap_count"] == 0
    assert proof["old_slice_overlap_count"] == 0
    assert proof["source_160_compact_cases_reused_for_validation"] is False


def test_next_candidate_specs_are_non_executable_and_child_scoped() -> None:
    spec = build_next_specs()
    assert spec["blockers"] == []
    assert spec["candidate_rule_generated"] is False
    assert spec["candidate_yaml_generated"] is False
    assert spec["candidate_jsonl_generated"] is False
    ids = {item["mechanism_id"] for item in spec["new_child_mechanisms"]}
    assert ids == {"missing_param_epistemic_gate_v0", "long_context_state_retrieval_v0"}


def test_next_result_remains_bounded_non_performance_evidence() -> None:
    result = json.loads((ROOT / "abhe_v0_next_dev_smoke_result.json").read_text())
    assert result["bounded_dev_smoke_only"] is True
    assert result["performance_evidence"] is False
    assert result["holdout_touched"] is False
    assert result["full_suite_touched"] is False
    assert result["archive_updated"] is False
    assert result["arm_compact_metrics"]["frozen_v2"]["passed_count"] >= result["arm_compact_metrics"]["baseline"]["passed_count"]


def test_next_matrix_discloses_scorer_unit_resolution() -> None:
    matrix = json.loads((ROOT / "abhe_v0_next_paired_case_matrix.json").read_text())
    assert matrix["strict_per_compact_case_paired_available"] is False
    assert matrix["strict_scorer_unit_paired_available"] is True
    assert matrix["performance_evidence"] is False
    assert matrix["archive_source_overlap_count"] == 0
