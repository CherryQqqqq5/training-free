# RASHE Phase B Compact Source Diagnostic Summary

Status: compact sanitized Phase B source diagnostic artifacts only. This note is not a performance, +3pp, Huawei, candidate, or scorer claim.

## Signed Scope

- signed route: `gpt-4.1`
- provider profile: `Chuangzhi/Novacode`
- category scope: `8 categories x 20 = 160`
- total provider call count: `160`
- total case count: `160`
- candidate_generation_authorized: `false`
- scorer_authorized: `false`
- performance_evidence: `false`
- Huawei/+3pp claim: `false`

## Category Counts

| category | case_count | provider_call_count | nonzero failure buckets |
| --- | ---: | ---: | --- |
| `agentic_memory` | 20 | 20 | `memory_not_retrieved=9, memory_update_when_should_search=11` |
| `agentic_web_search` | 20 | 20 | `answered_without_tool=2, fetch_missing_after_search=6, search_query_too_broad=11, wrong_first_tool=1` |
| `hallucination` | 20 | 20 | `unsupported_hallucinated_answer=20` |
| `irrelevance` | 20 | 20 | `irrelevant_tool_call=20` |
| `multi_turn_base` | 20 | 20 | `multi_turn_state_lost=20` |
| `multi_turn_long_context` | 20 | 20 | `multi_turn_state_lost=20` |
| `multi_turn_miss_func` | 20 | 20 | `multi_turn_state_lost=20` |
| `multi_turn_miss_param` | 20 | 20 | `multi_turn_state_lost=20` |

## Failure Bucket Totals

| bucket | count |
| --- | ---: |
| `answered_without_tool` | 2 |
| `fetch_missing_after_search` | 6 |
| `final_answer_before_tool` | 0 |
| `invalid_tool_call_format` | 0 |
| `irrelevant_tool_call` | 20 |
| `memory_not_retrieved` | 9 |
| `memory_update_when_should_search` | 11 |
| `multi_turn_state_lost` | 80 |
| `parser_schema_failure` | 0 |
| `search_query_too_broad` | 11 |
| `unsupported_hallucinated_answer` | 20 |
| `wrong_first_tool` | 1 |

## No-Leakage And Stop Gates

- raw_payload_tracked_count_total: `0`
- forbidden_field_violation_count_total: `0`
- raw prompt/case_id/gold/expected/reference/provider payload/scorer diff/candidate output/feedback persisted: `false`
- raw request/response/header/body persisted: `false`
- nonce-to-raw-case mapping persisted: `false`
- candidate JSONL/pool generated: `false`
- scorer/dev/holdout/full BFCL run: `false`
- performance/+3pp/Huawei artifact generated: `false`
- stop gate triggered: `false`

## Qualified Skill Threshold Note

The interpretation rule remains skill-level aggregate only: a future candidate-proposer approval packet may be prepared only if a skill's primary buckets aggregate to at least 12 counts across the 160 compact source cases and cover at least two categories. This summary does not authorize candidate generation or scorer execution.
