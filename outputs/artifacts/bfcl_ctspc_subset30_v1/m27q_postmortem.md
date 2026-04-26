# M2.7q Postmortem And Rule Retention

## Summary

- Evidence status: `durable`
- Trace mapping: `prompt_user_prefix`
- Case-level gate allowed: `True`
- Accuracy: baseline `13.33`, candidate `6.67`
- Fixed/regressed/net: `2` / `4` / `-2`
- Tool match rate: `0.6363636363636364`
- Raw arg match rate: `0.45454545454545453`
- Recommended next focus: `regression_and_rule_retention`

## Failed Gate Criteria

- `candidate_accuracy_gt_baseline_accuracy`
- `case_fixed_gt_regressed`
- `net_case_gain_min_2`
- `raw_arg_match_rate_min_0_6`

## Failure Layers

| Layer | Count |
| --- | ---: |
| `aligned_success` | 1 |
| `arg_match_low` | 2 |
| `fixed` | 2 |
| `not_activated` | 19 |
| `regression` | 4 |
| `tool_match_low` | 4 |
| `trajectory_continuation_or_postcondition` | 4 |

## Rule Retention

| Rule | Activations | Fixed | Regressed | Net | Tool Match | Arg Match | Trajectory Fails | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `rule_global_no_tool_actionable_no_tool_decision_prior_explicit_literals_present_prior_tool_outputs_present_tools_available_v1` | 13 | 0 | 0 | 0 | 0.5384615384615384 | 0.3076923076923077 | 4 | `reject` |
| `rule_global_no_tool_actionable_no_tool_decision_prior_tool_outputs_present_tools_available_v1` | 11 | 0 | 0 | 0 | 0.5454545454545454 | 0.36363636363636365 | 4 | `reject` |
| `rule_global_no_tool_post_tool_prose_summary_v1` | 12 | 1 | 0 | 1 | 0.5833333333333334 | 0.3333333333333333 | 3 | `reject` |

## Recommendations

- `do_not_rerun_m2_7f_on_this_30_case_dev_subset_without_new_offline_gate`
- `demote_or_reject_rules_with_nonpositive_net_case_gain`
- `keep_current_default_rule_decision_reject_unless_rule_has_positive_local_evidence`
