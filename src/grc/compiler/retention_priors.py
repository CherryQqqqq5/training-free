"""Theory-guided retention priors for training-free rule families.

Retention is intentionally split from benchmark performance. A rule must first
satisfy a principled invariant before dev/holdout evidence can move it toward
retained memory.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

NEVER_RETAIN = "never_retain"
DIAGNOSTIC_ONLY = "diagnostic_only"
DEMOTE_CANDIDATE = "demote_candidate"
RETAIN_CANDIDATE_AFTER_HOLDOUT = "retain_candidate_after_holdout"

RETENTION_CLASSES = {
    NEVER_RETAIN,
    DIAGNOSTIC_ONLY,
    DEMOTE_CANDIDATE,
    RETAIN_CANDIDATE_AFTER_HOLDOUT,
}

BFCL_FAILURE_REASONS = {
    "literal_not_emitted",
    "wrong_arg_key",
    "wrong_arg_value",
    "model_ignored_guidance",
    "scorer_trajectory_mismatch",
    "rule_not_applicable",
}

EXPLICIT_REQUIRED_ARG_LITERAL_FAMILY = "explicit_required_arg_literal_completion"
WRONG_ARG_KEY_ALIAS_FAMILY = "wrong_arg_key_alias_repair"
DETERMINISTIC_SCHEMA_LOCAL_NON_LIVE_FAMILY = "deterministic_schema_local_non_live_repair"


def _truthy(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def _base_prior(rule: dict[str, Any], eligibility: str, *, reason: str | None = None) -> dict[str, Any]:
    family = str(rule.get("rule_family") or rule.get("candidate_rules_type") or rule.get("rule_type") or "unknown")
    theory_class = "schema_constraint_completion" if family == EXPLICIT_REQUIRED_ARG_LITERAL_FAMILY else "none"
    intervention_scope = "argument_only" if family == EXPLICIT_REQUIRED_ARG_LITERAL_FAMILY else "unknown"
    if family == WRONG_ARG_KEY_ALIAS_FAMILY:
        theory_class = "schema_local_argument_normalization"
        intervention_scope = "argument_key_only"
    if family == DETERMINISTIC_SCHEMA_LOCAL_NON_LIVE_FAMILY:
        theory_class = "schema_local_deterministic_normalization"
        intervention_scope = "argument_value_or_call_shape_only"
    prior = {
        "rule_family": family,
        "theory_class": theory_class,
        "intervention_scope": intervention_scope,
        "trajectory_mutation": bool(rule.get("trajectory_mutation") or not rule.get("no_next_tool_intervention", False)),
        "tool_choice_mutation": bool(rule.get("tool_choice_mutation") or rule.get("exact_tool_choice") is True),
        "exact_tool_choice": bool(rule.get("exact_tool_choice") is True),
        "precondition_observable": False,
        "postcondition_local": False,
        "literal_source": "unknown",
        "retain_eligibility": eligibility,
    }
    if reason:
        prior["prior_rejection_reason"] = reason
    return prior


def explicit_required_arg_literal_prior(rule: dict[str, Any]) -> dict[str, Any]:
    """Return the theory prior for explicit required-arg literal completion.

    This family is retain-eligible in principle only when it stays local to
    schema argument completion: no next-tool mutation, no exact tool choice,
    observable literal evidence, and no ambiguous value.
    """
    family = str(rule.get("candidate_rules_type") or rule.get("rule_type") or "")
    if family != EXPLICIT_REQUIRED_ARG_LITERAL_FAMILY:
        return _base_prior(rule, NEVER_RETAIN, reason="unsupported_rule_family")

    literal = rule.get("literal_value")
    literal_ok = isinstance(literal, (str, int, float, bool)) and str(literal).strip() != "" and len(str(literal)) <= 240
    has_required_arg = bool(rule.get("required_arg") or rule.get("schema_arg_name"))
    no_tool_mutation = _truthy(rule.get("no_next_tool_intervention")) and rule.get("exact_tool_choice") is False and not _truthy(rule.get("ctspc_v0_action_rule"))
    source = str(rule.get("literal_source") or "")
    source_anchor = str(rule.get("literal_source_anchor") or rule.get("literal_source_observed_as") or "")
    directly_observable_sources = {"current_request", "current_observation", "current_request_or_current_observation"}
    observable_source = source in directly_observable_sources or (
        source == "source_result_tool_args" and source_anchor in directly_observable_sources
    )
    rejection = rule.get("rejection_reason")

    eligibility = DEMOTE_CANDIDATE
    reason = None
    if not literal_ok:
        eligibility = DIAGNOSTIC_ONLY
        reason = "missing_or_ambiguous_observable_literal"
    elif not has_required_arg:
        eligibility = DIAGNOSTIC_ONLY
        reason = "missing_required_arg_schema_binding"
    elif not observable_source:
        eligibility = DIAGNOSTIC_ONLY
        reason = "literal_source_not_observable"
    elif not no_tool_mutation:
        eligibility = NEVER_RETAIN
        reason = "trajectory_or_tool_choice_mutation"
    elif rejection:
        eligibility = DIAGNOSTIC_ONLY
        reason = str(rejection)

    prior = {
        "rule_family": EXPLICIT_REQUIRED_ARG_LITERAL_FAMILY,
        "theory_class": "schema_constraint_completion",
        "intervention_scope": "argument_only",
        "trajectory_mutation": False,
        "tool_choice_mutation": False,
        "exact_tool_choice": False,
        "precondition_observable": observable_source and literal_ok,
        "postcondition_local": True,
        "literal_source": "current_request_or_current_observation",
        "literal_source_observed_as": source or None,
        "literal_uniqueness": eligibility == DEMOTE_CANDIDATE,
        "schema_type_match": has_required_arg,
        "retain_eligibility": eligibility,
    }
    if reason:
        prior["prior_rejection_reason"] = reason
    return prior



def wrong_arg_key_alias_prior(rule: dict[str, Any]) -> dict[str, Any]:
    """Return the theory prior for schema-local argument key normalization."""
    family = str(rule.get("candidate_rules_type") or rule.get("rule_type") or "")
    if family != WRONG_ARG_KEY_ALIAS_FAMILY:
        return _base_prior(rule, NEVER_RETAIN, reason="unsupported_rule_family")

    original_key = str(rule.get("original_arg_key") or "")
    canonical_key = str(rule.get("canonical_arg_key") or rule.get("schema_arg_name") or "")
    arg_value = rule.get("arg_value")
    value_ok = isinstance(arg_value, (str, int, float, bool)) and str(arg_value).strip() != "" and len(str(arg_value)) <= 240
    alias_ok = bool(original_key and canonical_key and original_key != canonical_key and rule.get("alias_ambiguous") is not True)
    no_mutation = (
        _truthy(rule.get("no_next_tool_intervention"))
        and rule.get("exact_tool_choice") is False
        and not _truthy(rule.get("ctspc_v0_action_rule"))
        and rule.get("value_mutation") is False
        and rule.get("tool_choice_mutation") is False
        and rule.get("trajectory_mutation") is False
    )
    rejection = rule.get("rejection_reason")

    eligibility = DEMOTE_CANDIDATE
    reason = None
    if not alias_ok:
        eligibility = DIAGNOSTIC_ONLY
        reason = "missing_or_ambiguous_schema_alias"
    elif not value_ok:
        eligibility = DIAGNOSTIC_ONLY
        reason = "missing_or_mutated_arg_value"
    elif not no_mutation:
        eligibility = NEVER_RETAIN
        reason = "trajectory_tool_or_value_mutation"
    elif rejection:
        eligibility = DIAGNOSTIC_ONLY
        reason = str(rejection)

    prior = {
        "rule_family": WRONG_ARG_KEY_ALIAS_FAMILY,
        "theory_class": "schema_local_argument_normalization",
        "intervention_scope": "argument_key_only",
        "trajectory_mutation": False,
        "tool_choice_mutation": False,
        "value_mutation": False,
        "exact_tool_choice": False,
        "precondition_observable": value_ok and alias_ok,
        "postcondition_local": True,
        "alias_mapping_deterministic": eligibility == DEMOTE_CANDIDATE,
        "value_source": str(rule.get("value_source") or "model_emitted_args"),
        "retain_eligibility": eligibility,
    }
    if reason:
        prior["prior_rejection_reason"] = reason
    return prior




def deterministic_schema_local_non_live_prior(rule: dict[str, Any]) -> dict[str, Any]:
    """Return the theory prior for deterministic schema-local non-live repair."""
    family = str(rule.get("candidate_rules_type") or rule.get("rule_type") or "")
    if family != DETERMINISTIC_SCHEMA_LOCAL_NON_LIVE_FAMILY:
        return _base_prior(rule, NEVER_RETAIN, reason="unsupported_rule_family")

    deterministic = rule.get("schema_local_deterministic") is True
    tool_call_unique = rule.get("tool_call_mapping_unique") is True
    value_creation = rule.get("value_creation") is True
    gold_value_mutation = rule.get("gold_value_mutation") is True
    schema_ambiguous = rule.get("schema_match_ambiguous") is True or rule.get("repair_ambiguous") is True
    hidden_state = rule.get("hidden_state_category") is True or str(rule.get("category") or "") in {"memory", "memory_kv", "memory_rec_sum", "memory_vector"}
    has_values = rule.get("original_value") is not None and rule.get("normalized_value") is not None
    no_tool_mutation = (
        _truthy(rule.get("no_next_tool_intervention"))
        and rule.get("exact_tool_choice") is False
        and not _truthy(rule.get("ctspc_v0_action_rule"))
        and rule.get("tool_choice_mutation") is False
        and rule.get("trajectory_mutation") is False
    )
    rejection = rule.get("rejection_reason")

    eligibility = DEMOTE_CANDIDATE
    reason = None
    if hidden_state:
        eligibility = DIAGNOSTIC_ONLY
        reason = "memory_or_hidden_state_category_excluded"
    elif not deterministic or schema_ambiguous:
        eligibility = DIAGNOSTIC_ONLY
        reason = "ambiguous_or_non_deterministic_schema_repair"
    elif not tool_call_unique:
        eligibility = DIAGNOSTIC_ONLY
        reason = "parallel_call_mapping_not_unique"
    elif value_creation or gold_value_mutation or not has_values:
        eligibility = DIAGNOSTIC_ONLY
        reason = "value_creation_or_gold_value_mutation"
    elif not no_tool_mutation:
        eligibility = NEVER_RETAIN
        reason = "trajectory_or_tool_choice_mutation"
    elif rejection:
        eligibility = DIAGNOSTIC_ONLY
        reason = str(rejection)

    prior = {
        "rule_family": DETERMINISTIC_SCHEMA_LOCAL_NON_LIVE_FAMILY,
        "theory_class": "schema_local_deterministic_normalization",
        "intervention_scope": "argument_value_or_call_shape_only",
        "trajectory_mutation": False,
        "tool_choice_mutation": False,
        "exact_tool_choice": False,
        "gold_value_mutation": False,
        "value_creation": False,
        "schema_local_deterministic": deterministic,
        "precondition_observable": has_values and deterministic and tool_call_unique and not hidden_state,
        "postcondition_local": True,
        "repair_kind": str(rule.get("repair_kind") or "unknown"),
        "retain_eligibility": eligibility,
    }
    if reason:
        prior["prior_rejection_reason"] = reason
    return prior

def evaluate_retention_prior(rule: dict[str, Any]) -> dict[str, Any]:
    """Normalize or infer a rule retention prior.

    Missing priors are fail-closed. The one exception is the M2.8-pre explicit
    literal compiler family, where the prior can be inferred from candidate
    fields for backwards-compatible artifacts and tests.
    """
    provided = rule.get("retention_prior")
    family = str(rule.get("candidate_rules_type") or rule.get("rule_type") or "")
    if isinstance(provided, dict):
        prior = dict(provided)
        eligibility = str(prior.get("retain_eligibility") or NEVER_RETAIN)
        if eligibility not in RETENTION_CLASSES:
            eligibility = NEVER_RETAIN
            prior["prior_rejection_reason"] = "unknown_retain_eligibility"
        prior["retain_eligibility"] = eligibility
        prior.setdefault("rule_family", family or "unknown")
        prior.setdefault("theory_class", "none")
        prior.setdefault("intervention_scope", "unknown")
        prior.setdefault("trajectory_mutation", True)
        prior.setdefault("tool_choice_mutation", True)
        prior.setdefault("exact_tool_choice", bool(rule.get("exact_tool_choice") is True))
        prior.setdefault("precondition_observable", False)
        prior.setdefault("postcondition_local", False)
        prior.setdefault("literal_source", "unknown")
        return prior
    if family == EXPLICIT_REQUIRED_ARG_LITERAL_FAMILY:
        return explicit_required_arg_literal_prior(rule)
    if family == WRONG_ARG_KEY_ALIAS_FAMILY:
        return wrong_arg_key_alias_prior(rule)
    if family == DETERMINISTIC_SCHEMA_LOCAL_NON_LIVE_FAMILY:
        return deterministic_schema_local_non_live_prior(rule)
    return _base_prior(rule, NEVER_RETAIN, reason="missing_retention_prior")


def retain_prior_match(rule: dict[str, Any]) -> bool:
    prior = evaluate_retention_prior(rule)
    return prior.get("retain_eligibility") in {DEMOTE_CANDIDATE, RETAIN_CANDIDATE_AFTER_HOLDOUT}


def summarize_retention_priors(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        prior = evaluate_retention_prior(row)
        counts[str(prior.get("retain_eligibility") or NEVER_RETAIN)] += 1
    return {key: counts.get(key, 0) for key in [NEVER_RETAIN, DIAGNOSTIC_ONLY, DEMOTE_CANDIDATE, RETAIN_CANDIDATE_AFTER_HOLDOUT]}


def classify_bfcl_mismatch(row: dict[str, Any]) -> str:
    """Classify why a retain-eligible theory rule failed against scorer traces."""
    if not retain_prior_match(row):
        return "rule_not_applicable"
    if row.get("policy_plan_activated") is False or row.get("candidate_generatable") is False:
        return "literal_not_emitted"
    if row.get("key_mismatch") or row.get("arg_key_mismatch") or row.get("wrong_arg_key"):
        return "wrong_arg_key"
    if row.get("value_mismatch") or row.get("arg_value_mismatch") or row.get("wrong_arg_value"):
        return "wrong_arg_value"
    raw_match = row.get("raw_normalized_arg_match")
    final_match = row.get("final_normalized_arg_match")
    if raw_match is False or final_match is False:
        return "wrong_arg_value"
    if row.get("model_ignored_guidance") or row.get("emitted_arg_wrong_or_guidance_not_followed"):
        return "model_ignored_guidance"
    if row.get("trajectory_fail_count") or row.get("case_regressed") or row.get("primary_failure_layer") == "trajectory_continuation_or_postcondition":
        return "scorer_trajectory_mismatch"
    return "rule_not_applicable"
