# Batch2 Source Collection Pilot Snapshot

This artifact is compact progress evidence only. It is not candidate-pool, scorer, paired-comparison, or performance evidence.

## multi_turn_base

- source_collection_expansion_only: true
- candidate_pool_authorized: false
- scorer_authorized: false
- performance_evidence: false
- result_jsonl_rows: 20/20
- bad_result_rows: 0
- trace_count: 248
- exit_code: 124 (timeout_after_20_result_rows)
- selected_call_count: 47
- selected_calls_with_function_schema: 27
- selected_calls_with_required_args: 25
- selected_calls_with_missing_required: 0
- exactly_one: 0
- accepted: 0
- required_args_already_present_count: 34
- reject_reason_counts: `{"ambiguous_literal": 18, "no_single_missing_required_arg": 2}`
- unmatched_schema_reason_counts: `{"no exact/suffix/normalized schema alias matched emitted tool": 48}`

## multi_turn_long_context

- source_collection_expansion_only: true
- candidate_pool_authorized: false
- scorer_authorized: false
- performance_evidence: false
- result_jsonl_rows: 20/20
- bad_result_rows: 0
- trace_count: 225
- exit_code: 124 (timeout_after_20_result_rows)
- selected_call_count: 52
- selected_calls_with_function_schema: 32
- selected_calls_with_required_args: 30
- selected_calls_with_missing_required: 0
- exactly_one: 0
- accepted: 0
- required_args_already_present_count: 41
- reject_reason_counts: `{"ambiguous_literal": 18, "no_single_missing_required_arg": 2}`
- unmatched_schema_reason_counts: `{"no exact/suffix/normalized schema alias matched emitted tool": 50}`
