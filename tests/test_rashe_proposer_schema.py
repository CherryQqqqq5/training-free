import json
import subprocess
import sys
from pathlib import Path

from scripts.check_rashe_proposer_schema import check, reject_reason

SCRIPT = Path("scripts/check_rashe_proposer_schema.py")
FIXTURES = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/fixtures/proposal_drafts")
SCHEMA = Path("outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/proposal_draft.schema.json")


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_proposal_schema_has_allowed_kinds_and_fail_closed_fields():
    schema = json.loads(SCHEMA.read_text())
    assert set(schema["properties"]["proposal_kind"]["enum"]) == {
        "skill_metadata_refinement_draft",
        "progressive_disclosure_policy_draft",
        "router_policy_refinement_draft",
    }
    for field in [
        "offline_only",
        "enabled",
        "runtime_behavior_authorized",
        "prompt_injection_authorized",
        "retry_authorized",
        "candidate_generation_authorized",
        "scorer_authorized",
        "performance_evidence",
        "provider_call_count",
        "scorer_call_count",
        "source_collection_call_count",
    ]:
        assert field in schema["required"]


def test_accepts_synthetic_and_approved_compact_inert_proposals():
    for name in ["accept_skill_metadata_refinement.json", "accept_approved_compact_router_policy.json"]:
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


def test_rejects_forbidden_evidence_surfaces():
    assert reject_reason(load_fixture("reject_forbidden_gold.json")) == "forbidden_evidence"
    assert reject_reason(load_fixture("reject_candidate_output.json")) == "forbidden_evidence"


def test_rejects_raw_identifiers_and_raw_payloads():
    assert reject_reason(load_fixture("reject_raw_case_identifier.json")) == "raw_case_identifier"
    assert reject_reason(load_fixture("reject_raw_trace.json")) == "raw_trace_or_provider_payload"
    assert reject_reason(load_fixture("reject_raw_provider_payload.json")) == "raw_trace_or_provider_payload"


def test_rejects_source_scope_call_count_runtime_and_candidate_surfaces():
    assert reject_reason(load_fixture("reject_source_scope.json")) == "source_scope_not_allowed"
    assert reject_reason(load_fixture("reject_call_count_nonzero.json")) == "call_count_nonzero"
    assert reject_reason(load_fixture("reject_prompt_injection_text.json")) == "forbidden_runtime_or_candidate_surface"
    assert reject_reason(load_fixture("reject_candidate_kind.json")) == "proposal_kind_not_allowed"


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
    assert summary["proposer_schema_passed"] is True
    assert summary["proposal_fixture_count"] == 11
    assert summary["accepted_proposal_draft_count"] == 2
    assert summary["rejected_proposal_draft_count"] == 9
    assert summary["forbidden_evidence_reject_count"] == 2
    assert summary["raw_case_identifier_reject_count"] == 1
    assert summary["raw_trace_or_provider_payload_reject_count"] == 2
    assert summary["source_scope_reject_count"] == 1
    assert summary["call_count_nonzero_reject_count"] == 1
    assert summary["candidate_generation_authorized_count"] == 0
    assert summary["runtime_behavior_authorized_count"] == 0
    assert summary["prompt_injection_authorized_count"] == 0
    assert summary["scorer_authorized_count"] == 0
    assert summary["performance_evidence_count"] == 0
    assert summary["provider_call_count"] == 0
    assert summary["scorer_call_count"] == 0
    assert summary["source_collection_call_count"] == 0
