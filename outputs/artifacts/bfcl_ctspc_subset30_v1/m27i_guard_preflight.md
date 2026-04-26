# M2.7i Guard Preflight

- Passed: `False`
- Selected cases: `30`
- Before guard activations: `30`
- After guard activations: `2`
- Guard rejected cases: `28`
- Guard reasons: `{'intervention_mode_record_only': 147, 'pending_goal_postcondition_request_mismatch': 100, 'high_trajectory_risk': 54, 'explicit_literal_not_in_current_state': 52, 'cat_without_request_read_goal': 14}`
- After guard tool distribution: `{'cp': 1, 'mv': 1}`
- Dominant after guard rate: `0.5`
- Regressed status: `{'multi_turn_miss_param_9': 'guard_rejected', 'multi_turn_miss_param_21': 'guard_rejected', 'multi_turn_miss_param_36': 'guard_rejected'}`
- Fixed status: `{'multi_turn_miss_param_31': 'guard_rejected', 'multi_turn_miss_param_39': 'guard_rejected'}`
- First failed criterion: `guard_keeps_fixed_cases`

## Changed Cases

| Case | Status | Before Tool | After Tool | Guard Reasons |
| --- | --- | --- | --- | --- |
| multi_turn_miss_param_31 | guard_rejected | cat | None | intervention_mode_record_only, explicit_literal_not_in_current_state, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, intervention_mode_record_only, high_trajectory_risk, high_trajectory_risk, intervention_mode_record_only, intervention_mode_record_only, intervention_mode_record_only, explicit_literal_not_in_current_state, pending_goal_postcondition_request_mismatch |
| multi_turn_miss_param_9 | guard_rejected | touch | None | intervention_mode_record_only, explicit_literal_not_in_current_state, explicit_literal_not_in_current_state, cat_without_request_read_goal, explicit_literal_not_in_current_state, high_trajectory_risk, high_trajectory_risk, intervention_mode_record_only, intervention_mode_record_only, intervention_mode_record_only, intervention_mode_record_only, explicit_literal_not_in_current_state, cat_without_request_read_goal |
| multi_turn_miss_param_21 | guard_rejected | cat | None | pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, intervention_mode_record_only, intervention_mode_record_only, high_trajectory_risk, high_trajectory_risk, intervention_mode_record_only, intervention_mode_record_only, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, intervention_mode_record_only |
| multi_turn_miss_param_36 | guard_rejected | cat | None | explicit_literal_not_in_current_state, explicit_literal_not_in_current_state, intervention_mode_record_only, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, high_trajectory_risk, high_trajectory_risk, intervention_mode_record_only, pending_goal_postcondition_request_mismatch, explicit_literal_not_in_current_state, intervention_mode_record_only, intervention_mode_record_only, intervention_mode_record_only |
| multi_turn_miss_param_39 | guard_rejected | touch | None | intervention_mode_record_only, explicit_literal_not_in_current_state, explicit_literal_not_in_current_state, cat_without_request_read_goal, explicit_literal_not_in_current_state, intervention_mode_record_only, intervention_mode_record_only, intervention_mode_record_only, explicit_literal_not_in_current_state, cat_without_request_read_goal, intervention_mode_record_only, intervention_mode_record_only, intervention_mode_record_only |

## Interpretation

This checker is an offline source-trace replay. It gates whether the conservative action guard is precise enough to justify a later M2.7f-lite rerun; it is not BFCL performance evidence.
