# RASHE Stage 3 Evidence Index

Status: docs-only compact evidence chain. This file is an index of existing compact diagnostic and routing evidence; it does not authorize or request any executable downstream lane.

## Evidence Chain

- source diagnostics root: `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact`
- source diagnostics commit: `cc21c96b70ab51c2bf586c0e79cdde3838dcb05d`
- compact source cases: `160`
- total_source_cases: `160`
- candidate proposer approval packet: `outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_proposer_approval_packet.json`
- candidate proposals root: `outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_proposals`
- router proposer replay packet: `outputs/artifacts/stage1_bfcl_acceptance/rashe_offline_router_proposer_replay_packet.json`
- router proposer replay report: `outputs/artifacts/stage1_bfcl_acceptance/rashe_offline_router_proposer_replay.json`

## Compact Routing Counts

- `bfcl_multi_turn_state_tracking`: `80`
- `bfcl_hallucination_abstain`: `40`
- `no_spec_selected`: `40`

Fail-closed categories: `agentic_web_search`, `agentic_memory`.

Disallowed seed skills: `bfcl_web_search_decomposition`, `bfcl_memory_retrieve_before_answer`, `bfcl_parser_feedback_retry`.

## Verification

- `check_rashe_candidate_proposer_ready`: passed
- `check_rashe_offline_router_proposer_replay`: passed
- `check_artifact_boundary`: passed
- `stage3_evidence_index_json_consistency`: passed

## Boundaries

All execution, authorization, readiness, and downstream flags remain false: provider calls authorized/executed, BFCL generate/evaluate authorized/executed, scorer authorized/executed, full baseline, candidate JSONL authorized/created, candidate pool ready/created, candidate activation, dev/holdout material, performance evidence, SOTA claim, Huawei acceptance, and raw output persistence.

Next phase boundary: `future_separate_dev_scorer_approval_request_required`.
