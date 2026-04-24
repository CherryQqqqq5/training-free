# M2.7f Failure Diagnostic

M2.7f did not pass acceptance criteria. Do not expand to 100-case, M2.8, or full BFCL from this run.

## Acceptance Values

- `case_report_trace_mapping`: `mtime_by_result_step_count`
- `baseline_accuracy`: `10.0`
- `candidate_accuracy`: `13.33`
- `case_fixed_count`: `0`
- `case_regressed_count`: `0`
- `net_case_gain`: `0`
- `policy_plan_activated_count`: `29`
- `recommended_tool_match_rate_among_activated`: `0.27586206896551724`
- `raw_normalized_arg_match_rate_among_activated`: `0.0`
- `stop_allowed_false_positive_count`: `0`
- `accepted`: `False`

## Trace Mapping

Prompt-prefix mapping was rejected and the case report fell back to `mtime_by_result_step_count`; case-level attribution is diagnostic only.
- `baseline`: score_rows=27, expected_traces=465, prompt_prefix_mapped_traces=431, source_traces=468, missing_score_rows=['multi_turn_miss_param_21', 'multi_turn_miss_param_22', 'multi_turn_miss_param_25']
- `candidate`: score_rows=26, expected_traces=482, prompt_prefix_mapped_traces=421, source_traces=494, missing_score_rows=['multi_turn_miss_param_9', 'multi_turn_miss_param_25', 'multi_turn_miss_param_35', 'multi_turn_miss_param_39']

## Layer Diagnostic

- no activation cases: ['multi_turn_miss_param_37']
- selected_next_tool_distribution: {'mkdir': 29}
- recommended tool matches: 8/29
- raw normalized arg matches: 0/29
- case_fixed: []
- case_regressed: []
