# M2.7f Rule-Level Report

- trace mapping: `prompt_user_prefix`
- case-level gate allowed: `True`
- decisions: `{'retain': 0, 'demote': 0, 'reject': 3}`

| rule_id | activation | fixed | regressed | net | tool_match | arg_match | trajectory_fail | decision |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `rule_global_no_tool_actionable_no_tool_decision_prior_explicit_literals_present_prior_tool_outputs_present_tools_available_v1` | 13 | 0 | 0 | 0 | 0.538 | 0.308 | 4 | `reject` |
| `rule_global_no_tool_actionable_no_tool_decision_prior_tool_outputs_present_tools_available_v1` | 11 | 0 | 0 | 0 | 0.545 | 0.364 | 4 | `reject` |
| `rule_global_no_tool_post_tool_prose_summary_v1` | 12 | 1 | 0 | 1 | 0.583 | 0.333 | 3 | `reject` |
