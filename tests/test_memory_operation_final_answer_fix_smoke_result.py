from __future__ import annotations

import json
from pathlib import Path


def test_memory_final_answer_fix_smoke_uses_category_aggregate_scores() -> None:
    artifact = (
        Path(__file__).resolve().parents[1]
        / "outputs"
        / "artifacts"
        / "phase2"
        / "memory_operation_dev_smoke_v1"
        / "memory_operation_final_answer_fix_smoke_result.json"
    )

    report = json.loads(artifact.read_text(encoding="utf-8"))

    assert report["baseline_accuracy"] == 1.0
    assert report["candidate_accuracy"] == 1.0
    assert report["absolute_pp_delta"] == 0.0
    assert report["case_fixed_count"] == 0
    assert report["case_regressed_count"] == 0
    assert report["net_case_gain"] == 0
    assert report["no_last_message_cleared"] is True
    assert report["retain_rule_created"] is False
    assert report["bfcl_plus_3pp_claim"] is False
    assert report["holdout_authorized"] is False

    for side in ("baseline", "candidate"):
        assert report[side]["correct_count"] == 6
        assert report[side]["total_count"] == 6
        assert report[side]["final_answer_missing_count"] == 0
        assert all(row["scored_correct_by_category_aggregate"] for row in report[side]["records"])
