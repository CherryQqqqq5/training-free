# Schema Retrieval Rerank Feasibility Diagnostic

Offline deterministic lexical/schema-overlap audit over the raw-payload schema-not-matched bucket only. No embeddings, LLM/provider rerank, scorer target, candidates, or performance claim.

## Flags

- audit_only: `true`
- offline_only: `true`
- input_bucket: `raw_payload_schema_not_matched`
- input_case_count: `10`
- candidate_extraction_authorized: `false`
- candidate_pool_authorized: `false`
- paired_scoring_authorized: `false`
- scorer_authorization: `false`
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
| audited_bucket_case_count | 10 |
| raw_response_present_count | 10 |
| prompt_or_current_turn_present_count | 10 |
| dataset_schema_present_count | 10 |
| schema_option_count_total | 59 |
| forbidden_field_violation_count | 0 |
| single_schema_high_margin_count | 0 |
| top1_schema_margin_ge_threshold_count | 0 |
| top3_schema_non_ambiguous_count | 3 |
| all_schema_scores_tied_or_low_margin_count | 10 |
| multiple_high_margin_schema_candidates_count | 4 |
| no_retrievable_schema_signal_count | 0 |
| raw_emitted_tool_name_supports_top_schema_count | 1 |
| prompt_terms_support_top_schema_count | 10 |
| parameter_terms_support_top_schema_count | 4 |
| class_or_path_terms_support_top_schema_count | 0 |
| uses_gold_tool_identity_count | 0 |
| uses_gold_argument_value_count | 0 |
| uses_scorer_diff_count | 0 |
| would_change_arguments_count | 0 |
| would_change_call_count | 0 |
| would_change_call_order_count | 0 |
| ambiguous_rerank_reject_count | 4 |

## Stop Gates

- passed: `false`
- stop_reasons: `["single_schema_high_margin_below_3_of_10", "ambiguous_or_low_margin_at_least_6_of_10"]`
- recommendation: `stop_no_yield_research_review`
