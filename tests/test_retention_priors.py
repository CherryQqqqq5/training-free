from __future__ import annotations

from grc.compiler.retention_priors import (
    DEMOTE_CANDIDATE,
    DIAGNOSTIC_ONLY,
    NEVER_RETAIN,
    classify_bfcl_mismatch,
    evaluate_retention_prior,
    explicit_required_arg_literal_prior,
)


def _valid_explicit_rule() -> dict:
    return {
        "rule_type": "explicit_required_arg_literal_completion",
        "candidate_rules_type": "explicit_required_arg_literal_completion",
        "tool": "echo",
        "required_arg": "content",
        "schema_arg_name": "content",
        "literal_value": "hello",
        "literal_source": "current_request",
        "no_next_tool_intervention": True,
        "exact_tool_choice": False,
        "ctspc_v0_action_rule": False,
        "rejection_reason": None,
    }


def test_case_specific_or_signature_patch_defaults_to_never_retain() -> None:
    rule = {"case_id": "multi_turn_miss_param_39", "blocked_candidate_signature": "cat:{file_name}"}
    prior = evaluate_retention_prior(rule)
    assert prior["retain_eligibility"] == NEVER_RETAIN
    assert prior["prior_rejection_reason"] == "missing_retention_prior"


def test_ctspc_next_tool_trajectory_rule_is_not_retain_eligible() -> None:
    rule = {
        "rule_type": "ctspc_file_path_next_tool",
        "candidate_rules_type": "ctspc_file_path_next_tool",
        "ctspc_v0_action_rule": True,
        "no_next_tool_intervention": False,
        "exact_tool_choice": True,
    }
    prior = evaluate_retention_prior(rule)
    assert prior["retain_eligibility"] == NEVER_RETAIN


def test_explicit_required_arg_literal_completion_is_demote_candidate() -> None:
    prior = explicit_required_arg_literal_prior(_valid_explicit_rule())
    assert prior["rule_family"] == "explicit_required_arg_literal_completion"
    assert prior["theory_class"] == "schema_constraint_completion"
    assert prior["intervention_scope"] == "argument_only"
    assert prior["trajectory_mutation"] is False
    assert prior["tool_choice_mutation"] is False
    assert prior["exact_tool_choice"] is False
    assert prior["precondition_observable"] is True
    assert prior["postcondition_local"] is True
    assert prior["literal_source"] == "current_request_or_current_observation"
    assert prior["retain_eligibility"] == DEMOTE_CANDIDATE


def test_missing_or_ambiguous_literal_downgrades_explicit_family() -> None:
    rule = _valid_explicit_rule()
    rule["literal_value"] = ""
    prior = evaluate_retention_prior(rule)
    assert prior["retain_eligibility"] == DIAGNOSTIC_ONLY
    assert prior["prior_rejection_reason"] == "missing_or_ambiguous_observable_literal"


def test_bfcl_mismatch_categories_for_theory_prior_rules() -> None:
    rule = _valid_explicit_rule()
    rule["retention_prior"] = explicit_required_arg_literal_prior(rule)
    assert classify_bfcl_mismatch({**rule, "arg_key_mismatch": True}) == "wrong_arg_key"
    assert classify_bfcl_mismatch({**rule, "raw_normalized_arg_match": False}) == "wrong_arg_value"
    assert classify_bfcl_mismatch({**rule, "model_ignored_guidance": True}) == "model_ignored_guidance"
    assert classify_bfcl_mismatch({**rule, "case_regressed": True}) == "scorer_trajectory_mismatch"

from grc.compiler.retention_priors import wrong_arg_key_alias_prior


def _valid_alias_rule() -> dict:
    return {
        "rule_type": "wrong_arg_key_alias_repair",
        "candidate_rules_type": "wrong_arg_key_alias_repair",
        "tool": "cat",
        "original_arg_key": "filename",
        "canonical_arg_key": "file_name",
        "arg_value": "report.txt",
        "value_source": "model_emitted_args",
        "no_next_tool_intervention": True,
        "exact_tool_choice": False,
        "ctspc_v0_action_rule": False,
        "tool_choice_mutation": False,
        "trajectory_mutation": False,
        "value_mutation": False,
        "alias_ambiguous": False,
    }


def test_wrong_arg_key_alias_repair_is_demote_candidate() -> None:
    prior = wrong_arg_key_alias_prior(_valid_alias_rule())
    assert prior["rule_family"] == "wrong_arg_key_alias_repair"
    assert prior["theory_class"] == "schema_local_argument_normalization"
    assert prior["intervention_scope"] == "argument_key_only"
    assert prior["value_mutation"] is False
    assert prior["alias_mapping_deterministic"] is True
    assert prior["retain_eligibility"] == DEMOTE_CANDIDATE


def test_wrong_arg_key_alias_rejects_ambiguous_or_mutating_repairs() -> None:
    ambiguous = _valid_alias_rule()
    ambiguous["alias_ambiguous"] = True
    assert wrong_arg_key_alias_prior(ambiguous)["retain_eligibility"] == DIAGNOSTIC_ONLY

    mutating = _valid_alias_rule()
    mutating["value_mutation"] = True
    prior = evaluate_retention_prior(mutating)
    assert prior["retain_eligibility"] == NEVER_RETAIN
    assert prior["prior_rejection_reason"] == "trajectory_tool_or_value_mutation"


from grc.compiler.retention_priors import deterministic_schema_local_non_live_prior


def _valid_deterministic_rule() -> dict:
    return {
        "rule_type": "deterministic_schema_local_non_live_repair",
        "candidate_rules_type": "deterministic_schema_local_non_live_repair",
        "tool": "set_flag",
        "arg_key": "enabled",
        "original_value": "true",
        "normalized_value": True,
        "repair_kind": "boolean_string_normalization",
        "schema_local_deterministic": True,
        "tool_call_mapping_unique": True,
        "value_creation": False,
        "gold_value_mutation": False,
        "no_next_tool_intervention": True,
        "exact_tool_choice": False,
        "ctspc_v0_action_rule": False,
        "tool_choice_mutation": False,
        "trajectory_mutation": False,
    }


def test_deterministic_schema_local_repair_is_demote_candidate() -> None:
    prior = deterministic_schema_local_non_live_prior(_valid_deterministic_rule())
    assert prior["rule_family"] == "deterministic_schema_local_non_live_repair"
    assert prior["theory_class"] == "schema_local_deterministic_normalization"
    assert prior["intervention_scope"] == "argument_value_or_call_shape_only"
    assert prior["gold_value_mutation"] is False
    assert prior["retain_eligibility"] == DEMOTE_CANDIDATE


def test_deterministic_schema_local_rejects_value_creation_or_mutation() -> None:
    created = _valid_deterministic_rule()
    created["value_creation"] = True
    assert deterministic_schema_local_non_live_prior(created)["retain_eligibility"] == DIAGNOSTIC_ONLY

    mutating = _valid_deterministic_rule()
    mutating["exact_tool_choice"] = True
    prior = evaluate_retention_prior(mutating)
    assert prior["retain_eligibility"] == NEVER_RETAIN


def test_observable_output_contract_preservation_is_demote_candidate() -> None:
    from grc.compiler.retention_priors import DEMOTE_CANDIDATE, evaluate_retention_prior

    prior = evaluate_retention_prior({
        "rule_type": "observable_output_contract_preservation_v1",
        "output_contract_observable": True,
        "payload_parseable": True,
        "wrapper_only_repair": True,
        "value_creation": False,
        "argument_creation": False,
        "answer_synthesis": False,
        "payload_value_mutation": False,
        "tool_choice_mutation": False,
        "trajectory_mutation": False,
        "exact_tool_choice": False,
    })

    assert prior["retain_eligibility"] == DEMOTE_CANDIDATE
    assert prior["intervention_scope"] == "wrapper_or_container_only"


def test_observable_output_contract_rejects_answer_synthesis() -> None:
    from grc.compiler.retention_priors import NEVER_RETAIN, evaluate_retention_prior

    prior = evaluate_retention_prior({
        "rule_type": "observable_output_contract_preservation_v1",
        "output_contract_observable": True,
        "payload_parseable": True,
        "wrapper_only_repair": True,
        "value_creation": False,
        "argument_creation": False,
        "answer_synthesis": True,
        "payload_value_mutation": False,
        "tool_choice_mutation": False,
        "trajectory_mutation": False,
        "exact_tool_choice": False,
    })

    assert prior["retain_eligibility"] == NEVER_RETAIN
