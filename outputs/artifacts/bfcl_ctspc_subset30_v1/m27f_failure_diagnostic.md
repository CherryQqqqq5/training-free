# M2.7f Failure Diagnostic

M2.7f did not pass the explicit phase gate. Do not expand to 100-case, M2.8, or full BFCL from this run.

## Gate Result

- `m2_7f_gate_passed`: `False`
- `case_level_evidence`: `durable`
- `first_failed_criterion`: `candidate_accuracy_gt_baseline_accuracy`
- `failed_criteria`: `['candidate_accuracy_gt_baseline_accuracy', 'case_fixed_count_gt_case_regressed_count', 'net_case_gain_min_2', 'recommended_tool_match_rate_among_activated_min_0_6', 'raw_normalized_arg_match_rate_among_activated_min_0_6']`
- `recommended_next_focus`: `over_actuation_or_repair_interaction`

## Acceptance Values

- `case_report_trace_mapping`: `prompt_user_prefix`
- `baseline_accuracy`: `13.33`
- `candidate_accuracy`: `10.0`
- `case_fixed_count`: `2`
- `case_regressed_count`: `3`
- `net_case_gain`: `-1`
- `policy_plan_activated_count`: `30`
- `recommended_tool_match_rate_among_activated`: `0.36666666666666664`
- `raw_normalized_arg_match_rate_among_activated`: `0.03333333333333333`
- `stop_allowed_false_positive_count`: `0`
- `accepted`: `False`

## Layer Diagnostic

- artifact completeness passed: `True`
- candidate action diversity passed: `True`
- selected_next_tool_distribution: `{'cat': 17, 'touch': 8, 'mkdir': 5}`
- dominant_selected_next_tool_rate: `0.5666666666666667`
- no activation cases: `[]`
- recommended tool matches: `11/30`
- raw normalized arg matches: `1/30`
- case_fixed: `['multi_turn_miss_param_31', 'multi_turn_miss_param_39']`
- case_regressed: `['multi_turn_miss_param_9', 'multi_turn_miss_param_21', 'multi_turn_miss_param_36']`

## Interpretation

Trace attribution is stable via prompt-prefix mapping, but candidate performance regressed relative to baseline. The main remaining blockers are low recommended-tool match and very low argument binding success, with over-actuation or repair interaction as the next diagnostic focus.
