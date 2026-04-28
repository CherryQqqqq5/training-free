# Postcondition-Guided Trajectory Policy Family Card

Status: `review_required_before_runtime_integration`

This is an offline theory-prior family card. It does not enable runtime policy execution and does not authorize BFCL/model/scorer runs.

- Candidate count: `145`
- Risk distribution: `{'high': 10, 'low': 49, 'medium': 86}`
- Capability distribution: `{'copy': 6, 'create_file': 18, 'directory_navigation': 56, 'move_or_rename': 4, 'read_content': 18, 'search_or_find': 31, 'write_content': 12}`

## Theory Prior

A tool-use trajectory should not terminate in prose when an unsatisfied, observable postcondition can be advanced by an available schema-local tool. The policy recommends a capability/tool family, not a case-specific tool call or argument value.

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

## Negative Controls Required

- `activation_near_zero_on_no_toolless_failure_slices`
- `activation_near_zero_when_required_postcondition_already_satisfied`
- `no_activation_without_available_recommended_tool`
