# Selected-Call Structural Failure Attribution

This is an offline diagnostic artifact only. It is not candidate-pool, scorer, performance, SOTA, or Huawei acceptance evidence.

- parser_refined: `true`
- parser_refinement_scope: `standard response tool-call paths only; provider envelope and metadata ignored`
- prior_parser_failure_mode: `{"commit": "7f9a7955", "reject_reason_counts": {"multiple_tool_like_payloads": 30}, "suspected_artifact": "broad raw-response payload extraction counted provider envelope or metadata as tool-like payloads"}`

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
| rows_with_no_tool_call | 5 |
| rows_with_final_text_only | 4 |
| rows_with_final_text_and_tool_like_payload | 0 |
| rows_with_malformed_tool_call_json | 0 |
| rows_with_unparseable_arguments | 0 |
| rows_with_multiple_tool_like_payloads | 0 |
| malformed_tool_call_repair_eligible_count | 0 |
| final_before_tool_guard_eligible_count | 0 |
| raw_envelope_payload_count | 30 |
| raw_candidate_tool_call_count | 25 |
| raw_schema_matched_tool_call_count | 14 |
| legitimate_multi_tool_sequence_count | 0 |
| ambiguous_multiple_schema_matched_payloads | 0 |
| metadata_or_envelope_ignored_count | 240 |
| schema_matched_raw_payload_count | 14 |
| schema_valid_raw_payload_count | 14 |
| raw_response_text_present_count | 30 |
| bad_jsonl_rows | 0 |
| forbidden_field_violation_count | 0 |

- reject_reason_counts: `{"no_tool_like_payload": 5, "raw_payload_schema_not_matched": 11, "raw_payload_valid_no_structural_failure": 14}`
- blockers: `["structural_repair_eligible_count_zero"]`
- next_required_action: `research_review_required_do_not_expand`
