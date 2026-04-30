# Schema-Local Non-Live Repair Diagnostic

This is an offline diagnostic artifact only. It is not candidate-pool, scorer, performance, or Huawei acceptance evidence.

- diagnostic_only: `true`
- candidate_pool_authorized: `false`
- scorer_authorized: `false`
- performance_evidence: `false`
- huawei_acceptance_ready: `false`
- sota_3pp_claim_ready: `false`
- value_provenance: `baseline_emitted_args`
- schema_provenance: `dataset_tool_schema`
- default_or_example_value_source_used: `false`
- conversion rule: deterministic local conversion only; no fuzzy/semantic conversion

## Counters

| counter | value |
| --- | ---: |
| selected_call_count | 249 |
| selected_calls_with_function_schema | 129 |
| selected_calls_with_required_args | 120 |
| required_args_present_count | 167 |
| schema_local_checked_arg_count | 167 |
| schema_local_type_mismatch_count | 0 |
| numeric_string_to_integer_candidate_count | 0 |
| numeric_string_to_number_candidate_count | 0 |
| boolean_string_candidate_count | 0 |
| enum_case_normalization_candidate_count | 0 |
| singleton_array_wrap_candidate_count | 0 |
| schema_local_candidate_count | 0 |
| schema_local_repair_eligible_count | 0 |
| schema_local_ambiguous_count | 0 |
| schema_local_unsafe_conversion_count | 0 |
| schema_local_noop_already_valid_count | 165 |

- reject_reason_counts: `{"function_schema_not_matched": 120, "schema_local_no_conversion": 2, "schema_local_noop_already_valid": 165, "schema_required_empty": 9}`
- blockers: `["schema_local_repair_eligible_count_zero"]`
- next_recommended_action: `research_review_required_do_not_lower_standards`
