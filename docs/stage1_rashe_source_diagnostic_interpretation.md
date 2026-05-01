# Stage 1 RASHE Source Diagnostic Interpretation

Status: interpretation spec only. This document does not authorize candidate generation, scorer execution, provider re-runs, performance evidence, +3pp claims, or Huawei readiness.

## Primary Bucket Mapping

- `bfcl_web_search_decomposition`: `search_query_too_broad`, `fetch_missing_after_search`, `wrong_first_tool`
- `bfcl_memory_retrieve_before_answer`: `memory_not_retrieved`, `memory_update_when_should_search`
- `bfcl_multi_turn_state_tracking`: `multi_turn_state_lost`, `invalid_tool_call_format`
- `bfcl_parser_feedback_retry`: `parser_schema_failure`, `final_answer_before_tool`
- `bfcl_hallucination_abstain`: `unsupported_hallucinated_answer`, `answered_without_tool`, `irrelevant_tool_call`

## Candidate-Lane Entry Rule

A future candidate-proposer execution approval packet may be prepared only if a primary failure bucket count is at least `12/160` and that primary bucket is observed across at least `2` signed categories. If all primary bucket counts are below `12`, stop and return to skill design review. Do not proceed to scorer preparation from this diagnostic alone.

## Forbidden Interpretation Inputs

Do not inspect, quote, summarize, or persist raw prompts, raw case IDs, gold, expected, reference, scorer diff, provider raw payload, raw trace, candidate output, repair output, feedback, holdout feedback, or full-suite feedback.

## Claim Boundary

Compact source diagnostics may support failure-bucket triage only. They do not support performance evidence, BFCL +3pp claims, SOTA claims, or Huawei acceptance readiness.
