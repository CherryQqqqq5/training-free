# M2.7q Postmortem And Rule Retention

## Summary

- Evidence status: `durable`
- Trace mapping: `prompt_user_prefix`
- Case-level gate allowed: `True`
- Accuracy: baseline `6.67`, candidate `6.67`
- Fixed/regressed/net: `1` / `1` / `0`
- Tool match rate: `0.625`
- Raw arg match rate: `0.375`
- Recommended next focus: `binding_serialization_or_argument_realization`

## Failed Gate Criteria

- `candidate_accuracy_gt_baseline_accuracy`
- `case_fixed_gt_regressed`
- `net_case_gain_min_2`
- `raw_arg_match_rate_min_0_6`

## Failure Layers

| Layer | Count |
| --- | ---: |
| `aligned_success` | 1 |
| `arg_match_low` | 4 |
| `fixed` | 1 |
| `not_activated` | 14 |
| `regression` | 1 |
| `tool_match_low` | 6 |
| `trajectory_continuation_or_postcondition` | 5 |

## Rule Retention

| Rule | Activations | Fixed | Regressed | Net | Tool Match | Arg Match | Trajectory Fails | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `rule_global_no_tool_actionable_no_tool_decision_prior_explicit_literals_present_prior_tool_outputs_present_tools_available_v1` | 13 | 0 | 0 | 0 | 0.5384615384615384 | 0.3076923076923077 | 4 | `reject` |
| `rule_global_no_tool_actionable_no_tool_decision_prior_tool_outputs_present_tools_available_v1` | 11 | 0 | 0 | 0 | 0.5454545454545454 | 0.36363636363636365 | 4 | `reject` |
| `rule_global_no_tool_post_tool_prose_summary_v1` | 12 | 1 | 0 | 1 | 0.5833333333333334 | 0.3333333333333333 | 3 | `reject` |

## Recommendations

- `do_not_rerun_m2_7f_on_this_30_case_dev_subset_without_new_offline_gate`
- `plan_m2_7r_binding_serialization_and_argument_realization`
- `keep_current_default_rule_decision_reject_unless_rule_has_positive_local_evidence`
