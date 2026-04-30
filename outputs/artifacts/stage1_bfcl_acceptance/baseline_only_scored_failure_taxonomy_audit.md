# Baseline-Only Scored Failure Taxonomy Audit

This is scorer-output taxonomy only. It is not performance evidence and does not authorize candidate extraction, candidate pool promotion, paired comparison, dev/holdout/full scoring, or provider/model generation.

## Flags

- audit_only: `true`
- baseline_only: `true`
- candidate_extraction_authorized: `false`
- candidate_pool_authorized: `false`
- scorer_authorization_for_performance: `false`
- performance_evidence: `false`
- sota_3pp_claim_ready: `false`
- huawei_acceptance_ready: `false`

## Counters

| counter | value |
| --- | ---: |
| audited_case_count | 30 |
| scored_case_count | 30 |
| source_score_case_overlap_count | 22 |
| missing_score_count | 0 |
| bad_score_rows | 0 |
| route_model_matched_count | 22 |
| forbidden_field_violation_count | 0 |
| baseline_success_count | 8 |
| baseline_failure_count | 22 |
| baseline_success_rate | 0.266667 |
| baseline_failure_rate | 0.733333 |
| failure_with_no_tool_like_payload | 5 |
| failure_with_raw_payload_schema_not_matched | 10 |
| failure_with_selected_schema_not_matched | 0 |
| failure_with_schema_valid_selected_calls | 6 |
| failure_with_wrong_tool_or_order | 0 |
| failure_with_extra_or_missing_call_count | 1 |
| failure_with_argument_name_mismatch | 0 |
| failure_with_argument_value_mismatch | 0 |
| failure_with_execution_or_state_mismatch | 0 |
| unattributed_failure_count | 0 |

## Notes

- score_file_count: `3`
- raw_score_gold_bearing_rows_read_count: `22`; raw scorer rows were read only under aggregate-taxonomy authorization and no gold/expected content was emitted.
- aggregate_bucket_sample_hashes contain case-id hashes only, not case text, gold, expected values, scorer diffs, or repair recommendations.
- next_action: `research_review_only_do_not_expand_or_promote_candidate_pool`
