# M2.7aa Regression Patterns

- Passed: `False`
- Old unresolved regressions: `3`
- New regression patterns: `0`
- Regression pattern coverage: `1.0`
- Diagnostic unsafe gaps: `0`

## Regression / Gap Cases
- `multi_turn_miss_param_17`: `gap_only`, tool=`touch`, binding=`prior_tool_output.cwd_or_listing`, gap=`proxy_activated_but_scorer_not_activated`, guard=`diagnostic_only`
- `multi_turn_miss_param_19`: `gap_only`, tool=`cp`, binding=`explicit_literal_pair`, gap=`proxy_ok_trajectory_failed`, guard=`diagnostic_only`
- `multi_turn_miss_param_22`: `gap_only`, tool=`cat`, binding=`prior_tool_output.matches[0]|basename`, gap=`proxy_arg_ok_scorer_arg_wrong`, guard=`diagnostic_only`
- `multi_turn_miss_param_27`: `gap_only`, tool=`mv`, binding=`explicit_literal_pair`, gap=`proxy_ok_trajectory_failed`, guard=`diagnostic_only`
- `multi_turn_miss_param_28`: `gap_only`, tool=`cat`, binding=`prior_tool_output.matches[0]|basename`, gap=`proxy_tool_ok_scorer_tool_wrong`, guard=`diagnostic_only`
- `multi_turn_miss_param_29`: `gap_only`, tool=`cat`, binding=`prior_tool_output.matches[0]|basename`, gap=`proxy_tool_ok_scorer_tool_wrong`, guard=`diagnostic_only`
- `multi_turn_miss_param_30`: `gap_only`, tool=`cat`, binding=`prior_tool_output.matches[0]|basename`, gap=`proxy_activated_but_scorer_not_activated`, guard=`diagnostic_only`
- `multi_turn_miss_param_31`: `gap_only`, tool=`cat`, binding=`prior_tool_output.matches[0]|basename`, gap=`proxy_ok_trajectory_failed`, guard=`diagnostic_only`
- `multi_turn_miss_param_35`: `old_unresolved`, tool=`cat`, binding=`prior_tool_output.matches[0]|basename`, gap=`proxy_activated_but_scorer_not_activated`, guard=`record_only`
- `multi_turn_miss_param_39`: `old_unresolved`, tool=`touch`, binding=`prior_tool_output.cwd_or_listing`, gap=`proxy_arg_ok_scorer_arg_wrong`, guard=`record_only`
- `multi_turn_miss_param_4`: `gap_only`, tool=`cat`, binding=`prior_tool_output.matches[0]|basename`, gap=`proxy_tool_ok_scorer_tool_wrong`, guard=`diagnostic_only`
- `multi_turn_miss_param_5`: `gap_only`, tool=`cat`, binding=`prior_tool_output.matches[0]|basename`, gap=`proxy_tool_ok_scorer_tool_wrong`, guard=`diagnostic_only`
- `multi_turn_miss_param_9`: `old_unresolved`, tool=`None`, binding=`unknown`, gap=`no_proxy_gap`, guard=`record_only`

This is an offline pattern abstraction diagnostic. It does not run BFCL or prove scorer performance.
