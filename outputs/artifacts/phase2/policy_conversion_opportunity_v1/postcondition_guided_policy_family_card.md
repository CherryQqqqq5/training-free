# Postcondition-Guided Trajectory Policy Family Card

Status: `review_required_before_runtime_integration`

This is an offline theory-prior family card. It does not enable runtime policy execution and does not authorize BFCL/model/scorer runs.

- Candidate count: `145`
- Low-risk dry-run review eligible: `49`
- Risk distribution: `{'high': 10, 'low': 49, 'medium': 86}`
- Capability distribution: `{'copy': 6, 'create_file': 18, 'directory_navigation': 56, 'move_or_rename': 4, 'read_content': 18, 'search_or_find': 31, 'write_content': 12}`
- Ambiguity flags: `{'copy_move_destructive': 10, 'cue_only_match': 60, 'directory_vs_file_ambiguous': 16, 'multi_step_required': 26, 'state_mutating_capability': 96}`

## Theory Prior

A tool-use trajectory should not terminate in prose when an unsatisfied, observable postcondition can be advanced by an available schema-local tool. The policy recommends a capability/tool family only; it does not create arguments, force exact tool choice, or encode case-specific values.

## Hard Invariants

- `progress_invariant_unsatisfied_postcondition_only`
- `non_satisfaction_invariant_no_activation_when_witness_already_present`
- `schema_availability_invariant_recommended_tool_in_current_schema`
- `guidance_only_invariant_no_exact_tool_choice`
- `argument_non_creation_invariant_policy_recommends_capability_only`
- `state_mutation_invariant_medium_high_require_reviewer_approval`

## Admission Criteria

- `no_tool_policy_failure_label_present`
- `rule_hit_present`
- `prior_tool_observation_or_predicate_present`
- `recommended_tool_is_available_in_schema`
- `postcondition_witness_declared`
- `guidance_only`
- `exact_tool_choice_false`
- `no_target_or_scorer_field_dependency`

## Rejection Criteria

- `case_id_or_gold_answer_dependency`
- `recommended_tool_not_in_schema`
- `no_observable_prior_context`
- `destructive_or_state_mutating_tool_without_explicit_intent`
- `copy_move_or_directory_policy_without_reviewer_approval`
- `exact_tool_choice_required`
- `argument_creation_or_binding_not_allowed_in_this_family`

## Negative Controls Required

- `activation_near_zero_on_no_toolless_failure_slices`
- `activation_near_zero_when_required_postcondition_already_satisfied`
- `no_activation_without_available_recommended_tool`
- `no_activation_without_prior_observation`
- `destructive_false_positive_count_zero`
- `target_or_scorer_dependency_count_zero`

## First Runtime Review Boundary

Only `read_content` and `search_or_find` low-risk candidates may be considered for a later dry-run review. Medium/high risk capabilities remain diagnostic-only until explicitly approved.
