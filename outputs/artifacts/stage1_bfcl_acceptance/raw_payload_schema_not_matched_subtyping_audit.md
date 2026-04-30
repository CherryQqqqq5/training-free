# Raw Payload Schema-Not-Matched Subtyping Audit

Offline audit over the `failure_with_raw_payload_schema_not_matched` bucket only. It is not candidate extraction, not performance evidence, and not scorer/provider/source collection execution.

## Flags

- audit_only: `true`
- offline_only: `true`
- candidate_extraction_authorized: `false`
- candidate_pool_authorized: `false`
- scorer_authorization_for_performance: `false`
- provider_run_authorized: `false`
- source_collection_authorized: `false`
- candidate_run_authorized: `false`
- paired_comparison_authorized: `false`
- performance_evidence: `false`
- sota_3pp_claim_ready: `false`
- huawei_acceptance_ready: `false`
- gold_text_emitted: `false`
- expected_values_emitted: `false`
- per_case_repair_recommendations_emitted: `false`
- no_leakage_to_candidate_pool: `true`

## Counters

| counter | value |
| --- | ---: |
| raw_payload_schema_not_matched_failure_count | 10 |
| input_case_count | 10 |
| audited_bucket_case_count | 10 |
| raw_response_present_count | 10 |
| dataset_schema_present_count | 10 |
| forbidden_field_violation_count | 0 |
| emitted_tool_name_exact_schema_miss_count | 10 |
| emitted_tool_name_normalized_unique_match_count | 0 |
| case_insensitive_unique_match_count | 0 |
| punctuation_or_separator_unique_match_count | 0 |
| provider_namespace_or_path_alias_unique_match_count | 0 |
| qualified_short_name_unique_match_count | 0 |
| involved_class_or_path_unique_match_count | 0 |
| multiple_schema_name_candidates_count | 0 |
| no_schema_name_candidate_count | 10 |
| requires_gold_tool_identity_count | 0 |
| tool_selection_semantic_mismatch_count | 10 |
| unattributed_schema_not_matched_count | 0 |
| normalization_uses_gold_count | 0 |
| normalization_changes_arguments_count | 0 |
| normalization_changes_tool_order_count | 0 |
| normalization_changes_call_count | 0 |
| ambiguous_normalization_reject_count | 0 |
| deterministic_source_schema_only_possible_count | 0 |

## Decision

- recommendation: `stop_no_yield_research_review`
- no candidates were generated or authorized
