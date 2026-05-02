import json
from pathlib import Path

from scripts.check_bfcl_stage1_smoke_run_id_manifest import check, validate


MANIFEST = Path("outputs/artifacts/stage1_bfcl_acceptance/bfcl_stage1_smoke_run_id_manifest.json")


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def test_run_id_manifest_passes_prepared_fail_closed_state():
    summary = check(MANIFEST)
    assert summary["bfcl_stage1_smoke_run_id_manifest_passed"] is True
    assert summary["approval_status"] == "prepared"
    assert summary["route_model"] == "gpt-4.1"
    assert summary["total_case_count"] == 8
    assert summary["max_total_cases"] == 8
    assert summary["smoke_execution_authorized"] is False


def test_rejects_more_than_eight_cases():
    data = load_manifest()
    data["run_ids_by_category"]["simple_python"] = ["simple_python_0"]
    data["total_case_count"] = 9
    blockers = "\n".join(validate(data, validate_installed_ids=False))
    assert "smoke_run_id_total_case_count_exceeds_8:9" in blockers
    assert "smoke_run_id_run_ids_by_category_drift" in blockers


def test_rejects_duplicate_ids():
    data = load_manifest()
    data["run_ids_by_category"]["live_irrelevance"] = ["irrelevance_0"]
    blockers = "\n".join(validate(data, validate_installed_ids=False))
    assert "smoke_run_id_duplicate_run_ids" in blockers


def test_rejects_execution_or_provider_authorization():
    data = load_manifest()
    data["smoke_execution_authorized"] = True
    data["provider_call_authorized"] = True
    data["scorer_authorized"] = True
    blockers = "\n".join(validate(data))
    assert "smoke_run_id_smoke_execution_authorized_not_false:True" in blockers
    assert "smoke_run_id_provider_call_authorized_not_false:True" in blockers
    assert "smoke_run_id_scorer_authorized_not_false:True" in blockers


def test_rejects_route_drift_and_fallbacks():
    data = load_manifest()
    data["route_model"] = "gpt-5.2"
    data["gpt_4o_fallback_allowed"] = True
    data["openrouter_allowed"] = True
    blockers = "\n".join(validate(data))
    assert "smoke_run_id_route_model_invalid:'gpt-5.2'" in blockers
    assert "smoke_run_id_gpt_4o_fallback_allowed_not_false:True" in blockers
    assert "smoke_run_id_openrouter_allowed_not_false:True" in blockers


def test_rejects_candidate_and_performance_flags():
    data = load_manifest()
    data["candidate_runtime_activation_authorized"] = True
    data["candidate_jsonl_authorized"] = True
    data["candidate_pool_ready"] = True
    data["performance_evidence"] = True
    data["sota_3pp_claim_ready"] = True
    data["huawei_acceptance_ready"] = True
    blockers = "\n".join(validate(data))
    assert "smoke_run_id_candidate_runtime_activation_authorized_not_false:True" in blockers
    assert "smoke_run_id_candidate_jsonl_authorized_not_false:True" in blockers
    assert "smoke_run_id_candidate_pool_ready_not_false:True" in blockers
    assert "smoke_run_id_performance_evidence_not_false:True" in blockers
    assert "smoke_run_id_sota_3pp_claim_ready_not_false:True" in blockers
    assert "smoke_run_id_huawei_acceptance_ready_not_false:True" in blockers


def test_rejects_wrong_category_or_count():
    data = load_manifest()
    data["run_ids_by_category"]["memory_kv"].append("memory_kv_1-customer-1")
    blockers = "\n".join(validate(data, validate_installed_ids=False))
    assert "smoke_run_id_run_ids_by_category_drift" in blockers
    assert "smoke_run_id_per_category_count_invalid:memory_kv" in blockers


def test_rejects_run_id_not_in_installed_category():
    data = load_manifest()
    data["run_ids_by_category"]["web_search_base"] = ["web_search_base_missing"]
    blockers = "\n".join(validate(data))
    assert "smoke_run_id_not_in_installed_bfcl_category:web_search_base:web_search_base_missing" in blockers


def test_rejects_endpoint_or_key_literal():
    data = load_manifest()
    data["endpoint_url"] = "https" + "://example.invalid/v1"
    data["api_key"] = "sk-" + "F" * 24
    blockers = "\n".join(validate(data))
    assert "smoke_run_id_endpoint_literal_forbidden:endpoint_url" in blockers
    assert "smoke_run_id_key_literal_forbidden:api_key" in blockers


def test_rejects_scorer_feedback_enabled():
    data = load_manifest()
    data["scorer_feedback_enabled"] = True
    data["scorer_feedback_status"] = "enabled"
    blockers = "\n".join(validate(data))
    assert "smoke_run_id_scorer_feedback_enabled_not_false:True" in blockers
    assert "smoke_run_id_scorer_feedback_status_invalid:'enabled'" in blockers
