# Wrong Arg Key Alias Repair Diagnostic

This is an offline diagnostic artifact only. It is not candidate-pool, scorer, performance, or Huawei acceptance evidence.

- diagnostic_only: `true`
- candidate_pool_authorized: `false`
- scorer_authorized: `false`
- performance_evidence: `false`
- huawei_acceptance_ready: `false`
- sota_3pp_claim_ready: `false`
- source_value_provenance: `baseline_emitted_args`
- alias rule: deterministic `normalize_identifier_exact_match`; no fuzzy/semantic aliasing

## Counters

| counter | value |
| --- | ---: |
| selected_call_count | 249 |
| selected_calls_with_function_schema | 129 |
| selected_calls_with_required_args | 120 |
| required_arg_absent_by_canonical_key_count | 0 |
| emitted_alias_key_present_count | 0 |
| alias_map_unique_count | 0 |
| alias_value_schema_compatible_count | 0 |
| wrong_key_alias_candidate_count | 0 |
| alias_ambiguous_count | 0 |
| alias_type_mismatch_count | 0 |
| alias_repair_eligible_count | 0 |

- reject_reason_counts: `{"canonical_arg_already_present": 120, "function_schema_not_matched": 120, "schema_required_empty": 9}`
- blockers: `["wrong_arg_key_alias_repair_eligible_count_zero"]`
- next_recommended_diagnostic: `deterministic_schema_local_non_live_repair`
