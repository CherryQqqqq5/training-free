# RASHE Source Evidence Seed Skill Research Spec

Status: research/spec only. This document does not authorize candidate generation, candidate JSONL, scorer execution, performance evidence, or Huawei acceptance readiness.

Bounded source diagnostics may inform future seed-skill proposals only after separate candidate approval. Current Phase A records compact failure buckets and proposed trigger-policy-verifier structure; it does not generate or admit candidates.

## Trigger-Policy-Verifier Table

| Seed skill ID | Trigger | Policy | Verifier |
|---|---|---|---|
| `bfcl_web_search_decomposition` | `agentic_web_search` compact diagnostics with `answered_without_tool`, `wrong_first_tool`, `search_query_too_broad`, or `fetch_missing_after_search` buckets. | Decompose the user request into a bounded search query and fetch plan before final answer; require tool use when web evidence is needed. | Compact verifier checks no final answer before required search/fetch, no broad query bucket increase, no raw trace/provider payload/gold/expected/reference fields. |
| `bfcl_memory_retrieve_before_answer` | `agentic_memory` compact diagnostics with `memory_not_retrieved` or `memory_update_when_should_search` buckets. | Retrieve relevant memory before answering when the task references prior state; do not update memory when the proper action is search or retrieval. | Compact verifier checks retrieval-before-answer ordering, no memory-update-when-search bucket, no raw memory payload or case ID leakage. |
| `bfcl_multi_turn_state_tracking` | `multi_turn_base`, `multi_turn_long_context`, `multi_turn_miss_param`, or `multi_turn_miss_func` diagnostics with `multi_turn_state_lost`, `wrong_first_tool`, or `invalid_tool_call_format` buckets. | Carry forward required tool arguments and state across turns; prefer explicit state reconstruction before selecting a tool. | Compact verifier checks state keys are represented as hashes/counters only, required argument continuity is preserved, and no raw conversation trace is emitted. |
| `bfcl_parser_feedback_retry` | Any approved category with `invalid_tool_call_format`, `parser_schema_failure`, or `final_answer_before_tool` buckets. | On parser/schema failure, produce a bounded retry plan for format repair only; do not use scorer feedback or performance labels. | Compact verifier checks retry remains schema/format-local, candidate generation remains false, scorer_authorized remains false, and no scorer_diff/feedback fields appear. |
| `bfcl_hallucination_abstain` | `hallucination` or `irrelevance` diagnostics with `unsupported_hallucinated_answer`, `irrelevant_tool_call`, or `answered_without_tool` buckets. | Abstain or request needed evidence when tool support is missing; avoid unsupported final answers and irrelevant tool calls. | Compact verifier checks unsupported-answer bucket decreases in future approved tests, evidence state is hash/counter-only, and no raw trace/gold/expected/reference leakage occurs. |

## Candidate Admission Criteria For Later Approval Only

A future candidate lane would require separate approval and must show:

- source evidence from approved compact diagnostics only
- no raw trace, raw case ID, provider payload, gold, expected, scorer diff, candidate output, repair output, feedback, holdout feedback, or full-suite feedback
- deterministic trigger-policy-verifier description
- no scorer or performance feedback in proposal construction
- candidate generation authorization signed separately

Current status: candidate generation remains unauthorized.
