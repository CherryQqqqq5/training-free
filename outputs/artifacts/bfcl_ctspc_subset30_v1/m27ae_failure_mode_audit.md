# M2.7ae Failure-Mode Audit

- Passed: `True`
- Durable evidence: `True`
- Baseline/Candidate accuracy: `20.0` / `10.0`
- Net case gain: `-3`
- Regression sources: `{'action_policy': 1, 'no_tool_repair': 2, 'trajectory_continuation': 1}`
- First divergence layers: `{'argument_realization': 1, 'no_tool_repair': 2, 'trajectory_continuation': 1}`
- Route decision: `split_repair_stack + pivot_to_lower_risk_slice`

## Regression Cases
- `multi_turn_miss_param_38` source=`no_tool_repair` divergence=`no_tool_repair` repairs=`['coerce_no_tool_text_to_empty']`
- `multi_turn_miss_param_35` source=`no_tool_repair` divergence=`no_tool_repair` repairs=`['coerce_no_tool_text_to_empty', 'resolve_contextual_string_arg']`
- `multi_turn_miss_param_27` source=`trajectory_continuation` divergence=`trajectory_continuation` repairs=`['coerce_no_tool_text_to_empty', 'strip_assistant_content_with_tool_calls']`
- `multi_turn_miss_param_39` source=`action_policy` divergence=`argument_realization` repairs=`['coerce_no_tool_text_to_empty']`

This is an offline audit only. It does not authorize dev, holdout, 100-case, M2.8, or full BFCL scorer runs.
