# M2.7l Exact Tool-Choice Trajectory Diagnostic

- Case-level evidence: `diagnostic_only`
- Activated cases: `13`
- Exact tool-choice applied: `12`
- Action-specific guidance applied: `12`
- Failure layers: `{'selected_action_not_expected_trajectory': 17, 'local_tool_arg_match_but_trajectory_fail': 7, 'exact_tool_choice_overconstraint': 3, 'tool_arg_mismatch': 2, 'trace_mapping_incomplete': 1}`
- Missing candidate prompt-prefix traces: `['multi_turn_miss_param_43']`
- First failed criterion: `trace_mapping_incomplete`

| Case | Baseline | Candidate | Selected | Emitted | Exact | Tool+Arg | Layer |
| --- | --- | --- | --- | --- | --- | --- | --- |
| multi_turn_miss_param_17 | False | False | touch | ls | True | True | local_tool_arg_match_but_trajectory_fail |
| multi_turn_miss_param_19 | False | False | None | find | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_31 | False | False | cat | mkdir | True | True | local_tool_arg_match_but_trajectory_fail |
| multi_turn_miss_param_38 | False | False | None | find | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_3 | False | False | None | find | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_5 | False | False | cat | find | True | True | local_tool_arg_match_but_trajectory_fail |
| multi_turn_miss_param_7 | False | False | cat | mkdir | True | True | local_tool_arg_match_but_trajectory_fail |
| multi_turn_miss_param_16 | False | False | None | mkdir | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_22 | True | False | touch | ls | True | True | exact_tool_choice_overconstraint |
| multi_turn_miss_param_2 | False | False | cat | cd | True | False | tool_arg_mismatch |
| multi_turn_miss_param_6 | False | False | None | touch | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_9 | False | False | None | cd | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_10 | False | False | None | mkdir | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_18 | False | False | None | mkdir | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_21 | True | False | None | echo | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_28 | False | False | cat | find | True | True | local_tool_arg_match_but_trajectory_fail |
| multi_turn_miss_param_35 | True | False | cat | find | True | True | exact_tool_choice_overconstraint |
| multi_turn_miss_param_36 | False | False | None | touch | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_40 | False | False | touch | ls | True | True | local_tool_arg_match_but_trajectory_fail |
| multi_turn_miss_param_43 | False | False | touch | None | False | True | trace_mapping_incomplete |
| multi_turn_miss_param_45 | False | False | None | find | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_0 | False | False | None | mkdir | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_4 | False | False | None | ls | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_8 | False | False | None | grep | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_25 | False | False | None | ls | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_27 | False | False | cat | mv | True | True | local_tool_arg_match_but_trajectory_fail |
| multi_turn_miss_param_29 | False | False | None | cd | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_30 | False | False | None | find | False | False | selected_action_not_expected_trajectory |
| multi_turn_miss_param_37 | False | False | cat | cd | True | False | tool_arg_mismatch |
| multi_turn_miss_param_39 | True | False | touch | mkdir | True | True | exact_tool_choice_overconstraint |

This is an offline diagnostic. It is not BFCL performance evidence.
