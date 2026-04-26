# M2.7i Guard Preflight

- Passed: `True`
- Selected cases: `30`
- Before guard activations: `30`
- After guard activations: `10`
- Guard rejected cases: `20`
- Guard reasons: `{'pending_goal_postcondition_request_mismatch': 124, 'intervention_mode_record_only': 77, 'explicit_literal_not_in_current_state': 48, 'high_trajectory_risk': 42, 'cat_without_request_read_goal': 24, 'cat_competing_intent': 4, 'prior_output_state_unavailable': 2}`
- After guard tool distribution: `{'cat': 8, 'cp': 1, 'mv': 1}`
- Dominant after guard rate: `0.8`
- Regressed status: `{'multi_turn_miss_param_9': 'guard_rejected', 'multi_turn_miss_param_21': 'guard_rejected', 'multi_turn_miss_param_36': 'guard_rejected'}`
- Fixed status: `{'multi_turn_miss_param_31': 'guard_kept', 'multi_turn_miss_param_39': 'guard_kept'}`
- First failed criterion: `None`

## Changed Cases

| Case | Status | Before Tool | After Tool | Guard Reasons |
| --- | --- | --- | --- | --- |
| multi_turn_miss_param_31 | guard_kept | cat | cat | intervention_mode_record_only, explicit_literal_not_in_current_state, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, cat_competing_intent, high_trajectory_risk, high_trajectory_risk |
| multi_turn_miss_param_9 | guard_rejected | touch | None | intervention_mode_record_only, explicit_literal_not_in_current_state, explicit_literal_not_in_current_state, cat_without_request_read_goal, explicit_literal_not_in_current_state, high_trajectory_risk, high_trajectory_risk, cat_without_request_read_goal, intervention_mode_record_only, cat_without_request_read_goal, intervention_mode_record_only, explicit_literal_not_in_current_state, cat_without_request_read_goal |
| multi_turn_miss_param_21 | guard_rejected | cat | None | pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, intervention_mode_record_only, pending_goal_postcondition_request_mismatch, high_trajectory_risk, high_trajectory_risk, pending_goal_postcondition_request_mismatch, intervention_mode_record_only, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, intervention_mode_record_only |
| multi_turn_miss_param_36 | guard_rejected | cat | None | explicit_literal_not_in_current_state, explicit_literal_not_in_current_state, intervention_mode_record_only, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, high_trajectory_risk, high_trajectory_risk, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, explicit_literal_not_in_current_state, pending_goal_postcondition_request_mismatch, intervention_mode_record_only, intervention_mode_record_only |
| multi_turn_miss_param_39 | guard_kept | cat | cat | intervention_mode_record_only, explicit_literal_not_in_current_state, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch, pending_goal_postcondition_request_mismatch |

## Interpretation

This checker is an offline source-trace replay. It gates whether the conservative action guard is precise enough to justify a later M2.7f-lite rerun; it is not BFCL performance evidence.
