import json
from pathlib import Path

from scripts.check_bfcl_stage1_smoke_scope_manifest import check, validate


MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_stage1_smoke_scope_manifest.json")


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def test_smoke_scope_manifest_passes_pending_fail_closed_state():
    summary = check(MANIFEST)
    assert summary["bfcl_stage1_smoke_scope_manifest_passed"] is True
    assert summary["approval_status"] == "pending"
    assert summary["route_model"] == "gpt-4.1"
    assert summary["max_total_cases"] == 8
    assert summary["scope_enforceable_before_execution_now"] is False
    assert summary["smoke_execution_authorized"] is False


def test_rejects_more_than_eight_cases():
    data = load_manifest()
    data["required_future_scope"]["max_total_cases"] = 9
    assert "smoke_scope_max_total_cases_invalid:9" in validate(data)


def test_rejects_smoke_or_provider_authorization():
    data = load_manifest()
    data["smoke_execution_authorized"] = True
    data["provider_call_authorized"] = True
    blockers = "\n".join(validate(data))
    assert "smoke_scope_smoke_execution_authorized_not_false:True" in blockers
    assert "smoke_scope_provider_call_authorized_not_false:True" in blockers


def test_rejects_active_gpt_5_2_route():
    data = load_manifest()
    data["route_model"] = "gpt-5.2"
    assert "smoke_scope_route_model_invalid:'gpt-5.2'" in validate(data)


def test_rejects_gpt_4o_fallback_and_openrouter():
    data = load_manifest()
    data["gpt_4o_fallback_allowed"] = True
    data["openrouter_allowed"] = True
    blockers = "\n".join(validate(data))
    assert "smoke_scope_gpt_4o_fallback_allowed_not_false:True" in blockers
    assert "smoke_scope_openrouter_allowed_not_false:True" in blockers


def test_rejects_candidate_scorer_performance_claim_flags():
    data = load_manifest()
    data["candidate_runtime_activation_authorized"] = True
    data["candidate_jsonl_authorized"] = True
    data["candidate_pool_ready"] = True
    data["scorer_authorized"] = True
    data["performance_evidence"] = True
    data["sota_3pp_claim_ready"] = True
    data["huawei_acceptance_ready"] = True
    blockers = "\n".join(validate(data))
    assert "smoke_scope_candidate_runtime_activation_authorized_not_false:True" in blockers
    assert "smoke_scope_candidate_jsonl_authorized_not_false:True" in blockers
    assert "smoke_scope_candidate_pool_ready_not_false:True" in blockers
    assert "smoke_scope_scorer_authorized_not_false:True" in blockers
    assert "smoke_scope_performance_evidence_not_false:True" in blockers
    assert "smoke_scope_sota_3pp_claim_ready_not_false:True" in blockers
    assert "smoke_scope_huawei_acceptance_ready_not_false:True" in blockers


def test_rejects_raw_case_ids_or_nonce_mapping_committed():
    data = load_manifest()
    data["selected_case_ids"] = ["case_a"]
    data["required_future_scope"]["selected_case_ids_committed"] = True
    data["required_future_scope"]["nonce_or_raw_case_mapping_committed"] = True
    blockers = "\n".join(validate(data))
    assert "smoke_scope_raw_case_ids_committed:selected_case_ids" in blockers
    assert "smoke_scope_selected_case_ids_committed_not_false:True" in blockers
    assert "smoke_scope_nonce_or_raw_case_mapping_committed_not_false:True" in blockers


def test_rejects_endpoint_or_key_literal():
    data = load_manifest()
    data["endpoint_url"] = "https" + "://example.invalid/v1"
    data["api_key"] = "sk-" + "E" * 24
    blockers = "\n".join(validate(data))
    assert "smoke_scope_endpoint_literal_forbidden:endpoint_url" in blockers
    assert "smoke_scope_key_literal_forbidden:api_key" in blockers


def test_rejects_case_scope_as_enforceable_without_reviewed_manifest():
    data = load_manifest()
    data["existing_runner_scope_mechanism"]["scope_enforceable_before_execution_now"] = True
    data["existing_runner_scope_mechanism"]["reviewed_run_ids_manifest_present"] = True
    blockers = "\n".join(validate(data))
    assert "smoke_scope_runner_scope_enforceable_before_execution_now_invalid:True" in blockers
    assert "smoke_scope_runner_reviewed_run_ids_manifest_present_invalid:True" in blockers
