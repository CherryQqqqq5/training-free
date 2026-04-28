# Memory Operation Obligation Family Card

Status: `review_required_before_runtime_integration`

- Trace count: `151`
- Candidate count: `78`
- Candidate operation distribution: `{'retrieve': 78}`
- Candidate category distribution: `{'memory_kv': 30, 'memory_rec_sum': 48}`
- Witness strength distribution: `{'empty_or_error_witness': 44, 'no_witness': 69, 'weak_lookup_witness': 38}`
- Rejection reasons: `{'candidate_ready': 78, 'empty_or_error_memory_witness': 36, 'no_memory_operation_intent': 28, 'no_memory_tools_available': 9}`

## Theory Prior

When durable memory facts are requested and memory tools are schema-available, the agent should not answer from prose before an observable retrieve memory postcondition is satisfied.

## Admission Criteria

- `memory_tools_available`
- `retrieve_intent_observable_in_current_user_turn`
- `matching_memory_retrieve_tool_available_in_schema`
- `strong_memory_postcondition_witness_absent`
- `guidance_only`
- `exact_tool_choice_false`
- `no_gold_or_target_dependency`

## Rejection Criteria

- `delete_or_clear_operation_without_reviewer_approval`
- `write_family_not_yet_evidenced`
- `no_observable_memory_intent`
- `memory_postcondition_already_satisfied`
- `empty_or_error_memory_witness`
- `no_schema_available_memory_tool_for_operation`
- `hidden_target_or_gold_value_dependency`
- `argument_or_memory_value_creation`

## Negative Controls Required

- `no_activation_without_memory_tools`
- `no_activation_without_memory_intent`
- `no_activation_when_memory_postcondition_already_satisfied`
- `delete_false_positive_count_zero`

Offline audit only. This does not enable runtime policy execution or authorize BFCL/model/scorer runs.
