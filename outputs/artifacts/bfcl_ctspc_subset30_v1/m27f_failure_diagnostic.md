# M2.7f-lite post-M2.7k Failure Diagnostic

- gate passed: `False`
- case-level evidence: `diagnostic_only`
- first failed criterion: `case_report_trace_mapping`
- recommended next focus: `prompt_prefix_fallback`
- artifact completeness passed: `False`
- missing trace ids: `{'candidate': ['multi_turn_miss_param_43']}`

## Acceptance Values
- `case_report_trace_mapping`: `mtime_by_result_step_count`
- `baseline_accuracy`: `13.33`
- `candidate_accuracy`: `0.0`
- `case_fixed_count`: `0`
- `case_regressed_count`: `4`
- `net_case_gain`: `-4`
- `policy_plan_activated_count`: `13`
- `recommended_tool_match_rate_among_activated`: `1.0`
- `raw_normalized_arg_match_rate_among_activated`: `0.8461538461538461`
- `stop_allowed_false_positive_count`: `0`
- `accepted`: `False`

## Layer Diagnostic
- selected tool distribution: `{'cat': 8, 'touch': 5}`
- recommended tool matches: `13/13`
- raw normalized arg matches: `11/13`
- fixed cases: `[]`
- regressed cases: `['multi_turn_miss_param_22', 'multi_turn_miss_param_21', 'multi_turn_miss_param_35', 'multi_turn_miss_param_39']`

Do not expand to 100-case, M2.8, or full BFCL. This rerun is diagnostic-only because prompt-prefix trace mapping is incomplete.
