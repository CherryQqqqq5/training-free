from __future__ import annotations

from pathlib import Path

from scripts.build_abhe_v0_simple_candidates import build_outputs, validate_taxonomy
from scripts.plan_abhe_v0_archive_transition import build_plan
from scripts.score_abhe_v0_synthetic_dev_feedback import build_feedback

TAXONOMY = Path("abhe_archive/behavior_taxonomy_v0.json")


def test_taxonomy_is_small_two_level_baseline() -> None:
    outputs = build_outputs(TAXONOMY)
    policy = outputs["policy_score"]
    assert policy["abhe_v0_policy_score_passed"] is True
    assert len(policy["scored_entries"]) == 10
    assert policy["selected_entry_ids"] == ["state_tracking_v0", "hallucination_abstain_v0"]
    assert "search_query_or_fetch_failure_watch_v0" in policy["watch_entry_ids"]
    assert "memory_retrieve_update_confusion_watch_v0" in policy["watch_entry_ids"]


def test_taxonomy_validator_rejects_performance_evidence() -> None:
    outputs = build_outputs(TAXONOMY)
    taxonomy_like = {
        "artifact_kind": "abhe_behavior_taxonomy",
        "performance_evidence": True,
        "does_not_call_provider": True,
        "does_not_call_bfcl_or_model": True,
        "does_not_authorize_scorer": True,
        "does_not_generate_candidate_rule": True,
        "entries": outputs["policy_score"]["scored_entries"],
    }
    blockers = validate_taxonomy(taxonomy_like)
    assert "taxonomy_performance_evidence_not_false" in blockers


def test_candidate_specs_do_not_materialize_candidates() -> None:
    outputs = build_outputs(TAXONOMY)
    specs = outputs["candidate_specs"]
    assert specs["candidate_rule_generated"] is False
    assert specs["candidate_yaml_generated"] is False
    assert specs["candidate_jsonl_generated"] is False
    assert specs["candidate_generation_authorized"] is False
    assert all(spec["materialized"] is False for spec in specs["specs"])


def test_synthetic_slice_manifest_is_not_real_fresh_slice() -> None:
    outputs = build_outputs(TAXONOMY)
    manifest = outputs["slice_manifest"]
    assert manifest["synthetic_dry_run_only"] is True
    assert manifest["fresh_dev_slice_materialized"] is False
    assert manifest["source_160_compact_cases_reused_for_validation"] is False
    assert manifest["performance_evidence"] is False


def test_synthetic_feedback_and_transition_plan_are_fail_closed() -> None:
    outputs = build_outputs(TAXONOMY)
    candidate_path = Path("/tmp/abhe_v0_candidate_specs_test.json")
    candidate_path.write_text(__import__("json").dumps(outputs["candidate_specs"]), encoding="utf-8")
    feedback = build_feedback(candidate_path)
    assert feedback["abhe_v0_synthetic_dev_feedback_passed"] is True
    assert feedback["paired_dev_smoke_executed"] is False
    assert feedback["performance_evidence"] is False

    feedback_path = Path("/tmp/abhe_v0_feedback_test.json")
    feedback_path.write_text(__import__("json").dumps(feedback), encoding="utf-8")
    plan = build_plan(feedback_path)
    assert plan["abhe_v0_archive_transition_plan_passed"] is True
    assert plan["archive_updated"] is False
    assert plan["performance_evidence"] is False
    transitions = {row["entry_id"]: row["to_status"] for row in plan["planned_transitions"]}
    assert transitions == {
        "state_tracking_v0": "dev_passed",
        "hallucination_abstain_v0": "dev_passed",
    }
