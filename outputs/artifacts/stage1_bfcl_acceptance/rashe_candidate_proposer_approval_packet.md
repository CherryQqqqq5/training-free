# RASHE Candidate Proposer Approval Packet

Status: `pending` / fail-closed. This packet prepares candidate proposer approval materials only and does not authorize candidate execution.

## Signed Evidence

- source diagnostics commit: `cc21c96b70ab51c2bf586c0e79cdde3838dcb05d`
- route metadata: `gpt-4.1`
- source diagnostic root: `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact/`
- compact source diagnostic scope: `8 categories x 20 = 160`

## Allowed Seed Skills

- `bfcl_multi_turn_state_tracking`
- `bfcl_hallucination_abstain`

Disallowed: `bfcl_web_search_decomposition`, `bfcl_memory_retrieve_before_answer`, `bfcl_parser_feedback_retry`.

## Evidence Mapping

- `bfcl_multi_turn_state_tracking`: `multi_turn_state_lost=20` in `multi_turn_base`, `multi_turn_long_context`, `multi_turn_miss_param`, and `multi_turn_miss_func`.
- `bfcl_hallucination_abstain`: `unsupported_hallucinated_answer=20` in `hallucination`; `irrelevant_tool_call=20` in `irrelevance`.

## Allowed Inputs

Only compact diagnostics, failure bucket counts, frozen skill-to-bucket mapping, category coverage counts, no-leakage booleans, and `gpt-4.1` route metadata may be used for this approval preparation.

## Forbidden Material

Raw prompt, raw trace, provider request/response, case ID, gold, expected, reference, scorer diff, candidate output, repair feedback, holdout/full feedback, endpoint/key material, and source nonce mapping are forbidden.

## Authorization Boundary

- candidate_proposer_execution_authorized: `false`
- candidate_generation_authorized: `false`
- candidate_jsonl_authorized: `false`
- candidate_pool_ready: `false`
- scorer_authorized: `false`
- performance_evidence: `false`
- SOTA +3pp/Huawei readiness: `false`

This is not performance evidence, not a +3pp claim, not Huawei acceptance evidence, and not scorer evidence.
