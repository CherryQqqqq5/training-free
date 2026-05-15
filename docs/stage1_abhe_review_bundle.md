# Stage 1 ABHE Review Bundle

This document defines the approval-chain review bundle for ABHE. The bundle is a reviewer entrypoint, not an approval artifact, execution artifact, or performance evidence.

## Current State

ABHE is currently review-bundle ready and fail-closed:

- Planning readiness is prepared for review.
- Trace extraction packet remains pending.
- Trace card contract is defined, but no real trace cards are generated.
- Fresh dev slice request remains pending, and no fresh slice is materialized.
- Dev smoke packet remains pending.
- Dry-run runner gate is materialized, but it does not call provider, BFCL, or scorer.
- Granular approval schemas are defined for trace extraction, fresh dev slice, candidate spec review, and bounded dev smoke execution.
- No approved approval packet exists.
- Execution readiness remains false.

## Approval Chain

The review bundle points reviewers at separate approval lanes:

1. `trace_extraction_approval`
   - Future approval scope: `trace_cards_only`.
   - Allows only sanitized trace card creation within the approved output path and count.
   - Still forbids provider calls, BFCL generate/evaluate, scorer, candidate generation, and performance evidence.

2. `fresh_dev_slice_approval`
   - Future approval scope: `fresh_dev_slice_only`.
   - Allows only a fresh dev slice boundary to be approved.
   - Must keep archive seed sources excluded and must not reuse the 160 compact discovery cases for validation.
   - Still forbids provider calls, scorer, and performance evidence.

3. `candidate_spec_approval`
   - Future approval scope: `spec_review_only`.
   - Allows only candidate spec review to advance.
   - Does not authorize candidate rule generation, candidate JSONL, scorer, or performance evidence.

4. `execution_approval`
   - Future approval scope: `bounded_dev_smoke_only`.
   - Requires separate approved provider, model, protocol, runtime config, runner manifest hash, candidate spec hash, fresh dev slice hash, and case count.
   - Still forbids holdout, full suite, and performance claim authorization.

## Machine Gates

The following checkers keep the bundle fail-closed:

- `scripts/check_abhe_review_bundle.py`
- `scripts/check_abhe_approval_chain.py`
- `scripts/check_abhe_trace_extraction_approval_packet.py`
- `scripts/check_abhe_fresh_dev_slice_approval_packet.py`
- `scripts/check_abhe_candidate_spec_approval_packet.py`
- `scripts/check_abhe_execution_approval_packet.py`
- `scripts/check_abhe_execution_readiness.py`
- `scripts/check_abhe_no_leakage_boundary.py`

Missing approved packets are approval blockers, not planning failures. They prove execution is not yet authorized.

## Still Forbidden

Until explicit approved packets exist and the execution readiness checker passes, ABHE must not:

- Call providers.
- Run BFCL generate or evaluate.
- Run scorer.
- Generate candidate rules, YAML, JSONL, or candidate pool material.
- Extract real trace material.
- Materialize a fresh dev slice.
- Claim performance improvement, SOTA, +3pp, or Huawei acceptance readiness.

The review bundle must keep `execution_authorized=false`, `trace_extraction_authorized=false`, `fresh_dev_slice_authorized=false`, `candidate_generation_authorized=false`, `scorer_authorized=false`, `performance_evidence=false`, `sota_3pp_claim_ready=false`, and `huawei_acceptance_ready=false`.
