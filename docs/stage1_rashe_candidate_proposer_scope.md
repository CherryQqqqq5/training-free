# Stage 1 RASHE Candidate Proposer Scope

This document scopes bounded candidate proposer execution for spec-only artifacts over exactly two seed skills. Candidate generation, candidate JSONL generation, candidate pool readiness, scorer execution, performance evidence, +3pp claims, and Huawei acceptance remain unauthorized.

## Prepared Seed Skills

The only seed skills allowed in this pending approval packet are:

- `bfcl_multi_turn_state_tracking`
- `bfcl_hallucination_abstain`

The following seed skills are explicitly disallowed for this packet: `bfcl_web_search_decomposition`, `bfcl_memory_retrieve_before_answer`, and `bfcl_parser_feedback_retry`.

## Evidence Basis

- `bfcl_multi_turn_state_tracking`: compact Phase B diagnostics show `multi_turn_state_lost=20` in each of `multi_turn_base`, `multi_turn_long_context`, `multi_turn_miss_param`, and `multi_turn_miss_func`.
- `bfcl_hallucination_abstain`: compact Phase B diagnostics show `unsupported_hallucinated_answer=20` in `hallucination` and `irrelevant_tool_call=20` in `irrelevance`.

## Trigger-Policy-Verifier Boundary

- `bfcl_multi_turn_state_tracking`: trigger only from signed multi-turn state-loss compact bucket evidence; verifier checks frozen category coverage and no-leakage booleans before any future candidate packet can move out of pending.
- `bfcl_hallucination_abstain`: trigger only from signed hallucination/irrelevance abstention compact bucket evidence; verifier checks frozen category coverage and no-leakage booleans before any future candidate packet can move out of pending.

## Allowed Inputs

Allowed inputs are limited to compact diagnostics, failure bucket counts, frozen mapping, category coverage, no-leakage booleans, and route metadata for `gpt-4.1`.

## Forbidden Inputs And Outputs

Raw prompt, trace, provider request/response, case ID, gold, expected, reference, scorer diff, candidate output, repair feedback, holdout/full feedback, endpoint/key material, and source nonce mapping are forbidden. Candidate JSONL, candidate pool artifacts, scorer artifacts, performance artifacts, +3pp artifacts, and Huawei artifacts are not authorized.

This scope is not performance evidence, not a +3pp claim, not Huawei acceptance evidence, and not scorer evidence.

## Approved Execution Boundary

Bounded proposer execution is authorized only to write compact `SKILL.md` and `candidate_spec.json` review artifacts for `bfcl_multi_turn_state_tracking` and `bfcl_hallucination_abstain`. It must not create candidate JSONL, candidate pool artifacts, scorer inputs, performance artifacts, or Huawei/+3pp claims.
