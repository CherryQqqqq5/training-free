# RASHE Dev Scorer Approval Request

Status: pending request/template only. This document records a possible future review boundary and is not an execution packet.

Stage 3 is routing evidence only. It indexes compact source diagnostics, spec-only proposer artifacts, and the offline router/proposer replay report.

No execution is authorized by this request. Provider calls, BFCL generate/evaluate, scorer execution, full baseline, candidate JSONL, candidate pool creation, candidate activation, dev/holdout material use, and performance evidence remain false.

Separate future approval is required before any execution. Future review would need a scorer no-leakage gate, candidate materialization boundary, dev/holdout split policy, frozen commands, cost/latency/regression gates, stop-loss rules, and compact manifest cleanup policy.

## Evidence Pointers

- source diagnostics root: `outputs/artifacts/stage1_bfcl_acceptance/rashe_source_diagnostics_compact`
- source diagnostics commit: `cc21c96b70ab51c2bf586c0e79cdde3838dcb05d`
- candidate proposer approval packet: `outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_proposer_approval_packet.json`
- candidate proposals root: `outputs/artifacts/stage1_bfcl_acceptance/rashe_candidate_proposals`
- offline router/proposer replay report: `outputs/artifacts/stage1_bfcl_acceptance/rashe_offline_router_proposer_replay.json`
- Stage 3 evidence index: `outputs/artifacts/stage1_bfcl_acceptance/rashe_stage3_evidence_index.json`

## Stage 3 Counts

- `bfcl_multi_turn_state_tracking`: `80`
- `bfcl_hallucination_abstain`: `40`
- `no_spec_selected`: `40`
- `total_source_cases`: `160`

Fail-closed categories: `agentic_web_search`, `agentic_memory`.

Disallowed seed skills: `bfcl_web_search_decomposition`, `bfcl_memory_retrieve_before_answer`, `bfcl_parser_feedback_retry`.

## Current Boundary

- approval_status: `pending`
- authorized: `false`
- execution_packet: `false`
- request_scope: `future_dev_scorer_approval_request_only`
- requested_future_scope: `dev_scorer_approval_request_only_not_authorized`
