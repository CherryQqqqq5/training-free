# Stage 1 RASHE Source Diagnostic Interpretation

Status: interpretation spec only. This document does not authorize candidate generation, scorer execution, provider re-runs, performance evidence, +3pp claims, or Huawei readiness.

## Frozen Skill Primary Bucket Mapping

- `bfcl_web_search_decomposition`: `answered_without_tool`, `wrong_first_tool`, `search_query_too_broad`, `fetch_missing_after_search`
- `bfcl_memory_retrieve_before_answer`: `memory_not_retrieved`, `memory_update_when_should_search`, `final_answer_before_tool`
- `bfcl_multi_turn_state_tracking`: `multi_turn_state_lost`, `wrong_first_tool`, `final_answer_before_tool`
- `bfcl_parser_feedback_retry`: `invalid_tool_call_format`, `parser_schema_failure`
- `bfcl_hallucination_abstain`: `unsupported_hallucinated_answer`, `irrelevant_tool_call`

No extra primary buckets are signed for these seed skills, and missing buckets invalidate the interpretation gate.

## Candidate-Lane Entry Rule

A future candidate-proposer execution approval packet may be prepared only if a skill-level aggregate count across that skill's frozen primary buckets is at least `12/160` across the 160 signed source cases and those contributing primary buckets cover at least `2` signed categories. This is a skill-level aggregate threshold, not a single-bucket threshold. If every skill-level aggregate is below `12`, stop and return to skill design review. Do not proceed to scorer preparation from this diagnostic alone.

## Forbidden Interpretation Inputs

Do not inspect, quote, summarize, or persist raw prompts, raw case IDs, gold, expected, reference, scorer diff, provider raw payload, raw trace, candidate output, repair output, feedback, holdout feedback, or full-suite feedback.

## Claim Boundary

Compact source diagnostics may support failure-bucket triage only. They do not support performance evidence, BFCL +3pp claims, SOTA claims, or Huawei acceptance readiness.
