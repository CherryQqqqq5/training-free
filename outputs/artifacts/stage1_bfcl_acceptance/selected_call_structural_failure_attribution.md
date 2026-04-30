# Selected-Call Structural Failure Attribution

This is an offline diagnostic artifact only. It is not candidate-pool, scorer, performance, SOTA, or Huawei acceptance evidence.

- diagnostic_only: `true`
- candidate_pool_authorized: `false`
- scorer_authorized: `false`
- performance_evidence: `false`
- huawei_acceptance_ready: `false`
- sota_3pp_claim_ready: `false`
- raw traces remain untracked; no provider/scorer/source collection was run

## Counters

| counter | value |
| --- | ---: |
| result_jsonl_rows | 90 |
| raw_response_present_count | 0 |
| selected_call_count | 249 |
| schema_matched_selected_call_count | 129 |
| schema_valid_required_args_present_count | 129 |
| rows_with_no_tool_call | 0 |
| rows_with_final_text_only | 0 |
| rows_with_final_text_and_tool_like_payload | 0 |
| rows_with_malformed_tool_call_json | 0 |
| rows_with_unparseable_arguments | 0 |
| rows_with_multiple_tool_like_payloads | 0 |
| malformed_tool_call_repair_eligible_count | 0 |
| final_before_tool_guard_eligible_count | 0 |

- reject_reason_counts: `{"raw_response_missing_for_structural_attribution": 90}`
- blockers: `["raw_response_field_missing_for_structural_attribution", "structural_repair_eligible_count_zero"]`
- next_required_action: `research_review_required_missing_raw_response_field`
