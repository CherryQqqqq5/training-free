from grc.compiler.retention_priors import DEMOTE_CANDIDATE, evaluate_retention_prior
from scripts.diagnose_explicit_obligation_observable_capability import evaluate


def test_explicit_obligation_prior_accepts_readonly_soft_guidance():
    prior = evaluate_retention_prior({
        "rule_type": "explicit_obligation_to_observable_capability_v1",
        "explicit_obligation_present": True,
        "compatible_witness_status": "unmet_strong",
        "capability_risk_tier": "readonly_low",
        "recommended_capability_family": "read_content",
        "soft_guidance_only": True,
        "exact_tool_choice": False,
        "argument_creation": False,
        "tool_choice_mutation": False,
        "trajectory_mutation": False,
        "forbidden_dependency_present": False,
    })
    assert prior["retain_eligibility"] == DEMOTE_CANDIDATE


def test_explicit_obligation_prior_rejects_argument_creation():
    prior = evaluate_retention_prior({
        "rule_type": "explicit_obligation_to_observable_capability_v1",
        "explicit_obligation_present": True,
        "compatible_witness_status": "unmet_strong",
        "capability_risk_tier": "readonly_low",
        "recommended_capability_family": "read_content",
        "soft_guidance_only": True,
        "exact_tool_choice": False,
        "argument_creation": True,
        "tool_choice_mutation": False,
        "trajectory_mutation": False,
        "forbidden_dependency_present": False,
    })
    assert prior["retain_eligibility"] == "never_retain"


def test_obligation_audit_keeps_single_family_not_smoke_ready(tmp_path):
    report = evaluate(memory_path=tmp_path / "missing.json", unmet_path=tmp_path / "missing.json", directory_path=tmp_path / "missing.json")
    assert report["eligible_candidate_count"] == 0
    assert report["smoke_ready"] is False
    assert report["candidate_commands"] == []
    assert report["planned_commands"] == []
