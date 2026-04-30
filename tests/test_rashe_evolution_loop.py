import json
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_evolution_loop import check, reject_reason

SCRIPT = Path("scripts/check_rashe_evolution_loop.py")
FIXTURES = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/fixtures/evolution_loop")
SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/evolution_loop.schema.json")


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_evolution_schema_requires_full_offline_chain():
    schema = json.loads(SCHEMA.read_text())
    required = set(schema["required"])
    assert {
        "trace_buffer_summary",
        "router_decision_summary",
        "proposal_draft",
        "human_review",
        "skill_metadata_patch_plan",
    } <= required
    assert schema["properties"]["skill_metadata_patch_plan"]["properties"]["patch_plan_kind"]["enum"] == ["inert_docs_metadata_patch_plan"]


def test_accepts_inert_synthetic_and_approved_compact_loops():
    for name in ["accept_synthetic_skill_metadata_loop.json", "accept_approved_compact_router_loop.json"]:
        payload = load_fixture(name)
        assert reject_reason(payload) is None
        assert payload["offline_only"] is True
        assert payload["enabled"] is False
        assert payload["runtime_behavior_authorized"] is False
        assert payload["prompt_injection_authorized"] is False
        assert payload["retry_authorized"] is False
        assert payload["candidate_generation_authorized"] is False
        assert payload["scorer_authorized"] is False
        assert payload["performance_evidence"] is False
        assert payload["provider_call_count"] == 0
        assert payload["scorer_call_count"] == 0
        assert payload["source_collection_call_count"] == 0


def test_rejects_forbidden_evidence_call_count_scope_kind_and_auth():
    assert reject_reason(load_fixture("reject_forbidden_gold.json")) == "forbidden_evidence"
    assert reject_reason(load_fixture("reject_call_count_nonzero.json")) == "call_count_nonzero"
    assert reject_reason(load_fixture("reject_source_scope.json")) == "source_scope_not_allowed"
    assert reject_reason(load_fixture("reject_proposal_kind.json")) == "proposal_kind_not_allowed"
    assert reject_reason(load_fixture("reject_auth_flag.json")) == "auth_flag_true"


def test_rejects_prompt_and_dev_holdout_patch_plan_surfaces():
    assert reject_reason(load_fixture("reject_prompt_injection_patch_plan.json")) == "forbidden_patch_plan_surface"
    assert reject_reason(load_fixture("reject_dev_holdout_manifest_patch_plan.json")) == "forbidden_patch_plan_surface"


def test_checker_compact_report_passes_with_expected_counters():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--compact", "--strict"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["evolution_loop_schema_passed"] is True
    assert summary["loop_fixture_count"] == 9
    assert summary["accepted_loop_count"] == 2
    assert summary["rejected_loop_count"] == 7
    assert summary["forbidden_evidence_reject_count"] == 1
    assert summary["call_count_reject_count"] == 1
    assert summary["auth_flag_reject_count"] == 1
    assert summary["blocked_reason_counts"] == {
        "auth_flag_true": 1,
        "call_count_nonzero": 1,
        "forbidden_evidence": 1,
        "forbidden_patch_plan_surface": 2,
        "proposal_kind_not_allowed": 1,
        "source_scope_not_allowed": 1,
    }
    assert summary["source_scope_counts"] == {"approved_compact": 1, "dev_only_future": 1, "synthetic": 7}
    assert summary["candidate_generation_authorized_count"] == 0
    assert summary["scorer_authorized_count"] == 0
    assert summary["performance_evidence_count"] == 0
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
