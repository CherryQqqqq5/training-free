# M2.7f-lite Failure Diagnostic

- gate passed: False
- case-level evidence: durable
- first failed criterion: recommended_tool_match_rate_among_activated_min_0_6
- recommended next focus: actuation_or_prompt_guidance

## Acceptance Values
- case_report_trace_mapping: prompt_user_prefix
- baseline_accuracy: 6.67
- candidate_accuracy: 16.67
- case_fixed_count: 4
- case_regressed_count: 1
- net_case_gain: 3
- policy_plan_activated_count: 14
- recommended_tool_match_rate_among_activated: 0.42857142857142855
- raw_normalized_arg_match_rate_among_activated: 0.14285714285714285
- stop_allowed_false_positive_count: 0
- accepted: False

## Auxiliary Engineering Signal
- candidate_accuracy_gte_baseline_accuracy: True
- case_regressed_count_lte_1: True
- net_case_gain_gte_0: True
- policy_plan_activated_count_gte_10: True

## Layer Diagnostic
- selected tool distribution: {'cat': 9, 'touch': 5}
- recommended tool matches: 6/14
- raw normalized arg matches: 2/14
- fixed cases: ['multi_turn_miss_param_31', 'multi_turn_miss_param_22', 'multi_turn_miss_param_25', 'multi_turn_miss_param_39']
- regressed cases: ['multi_turn_miss_param_35']

Do not expand to 100-case, M2.8, or full BFCL from this result.
