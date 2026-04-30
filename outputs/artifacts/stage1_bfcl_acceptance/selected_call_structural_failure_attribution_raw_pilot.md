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
| result_jsonl_rows | 30 |
| raw_response_present_count | 30 |
| selected_call_count | 79 |
| schema_matched_selected_call_count | 45 |
| schema_valid_required_args_present_count | 45 |
| rows_with_no_tool_call | 0 |
| rows_with_final_text_only | 0 |
| rows_with_final_text_and_tool_like_payload | 0 |
| rows_with_malformed_tool_call_json | 0 |
| rows_with_unparseable_arguments | 0 |
| rows_with_multiple_tool_like_payloads | 30 |
| malformed_tool_call_repair_eligible_count | 0 |
| final_before_tool_guard_eligible_count | 0 |
| schema_matched_raw_payload_count | 0 |
| schema_valid_raw_payload_count | 0 |
| raw_response_text_present_count | 30 |
| bad_jsonl_rows | 0 |
| forbidden_field_violation_count | 0 |

- reject_reason_counts: `{"multiple_tool_like_payloads": 30}`
- blockers: `["structural_repair_eligible_count_zero"]`
- next_required_action: `research_review_required_do_not_expand`

## Input Health

- result_jsonl_rows: 30
- raw_response_present_count: 30
- raw_response_present_ratio: 1.0
- bad_jsonl_rows: 0
- forbidden_field_violation_count: 0
- provider_route_counts: `{\"Chuangzhi/Novacode\": 30}`
- model_id_counts: `{\"gpt-5.2\": 30}`

## Decision Gate

Eligible structural count is 0, so recommendation is research review; do not expand.

## BFCL Path Alias Note

BFCL directory/model path names such as `gpt-4o-mini-2024-07-18-FC` are non-authoritative runner/path aliases only. The authoritative provider/model are Chuangzhi/Novacode and `gpt-5.2`.
