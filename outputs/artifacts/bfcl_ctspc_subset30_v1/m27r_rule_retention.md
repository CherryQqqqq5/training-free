# M2.7r Rule Retention

- Ready: `True`
- Decision distribution: `{'retain': 0, 'demote': 0, 'reject': 3}`

| Rule | Activations | Fixed | Regressed | Net | Tool Match | Arg Match | Traj Fails | Not Activated | Decision | Reason |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `rule_global_no_tool_actionable_no_tool_decision_prior_explicit_literals_present_prior_tool_outputs_present_tools_available_v1` | 13 | 0 | 0 | 0 | 0.5384615384615384 | 0.3076923076923077 | 4 | 17 | `reject` | `no_positive_net_case_gain` |
| `rule_global_no_tool_actionable_no_tool_decision_prior_tool_outputs_present_tools_available_v1` | 11 | 0 | 0 | 0 | 0.5454545454545454 | 0.36363636363636365 | 4 | 19 | `reject` | `no_positive_net_case_gain` |
| `rule_global_no_tool_post_tool_prose_summary_v1` | 12 | 1 | 0 | 1 | 0.5833333333333334 | 0.3333333333333333 | 3 | 18 | `reject` | `tool_match_rate_below_retention_floor` |
