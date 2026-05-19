# Stage-1 RASHE External Handoff Note

This note is the external-facing handoff scope for the current `main` branch after the Stage-1 RASHE merge and post-runtime L1 approval. It is not a BFCL performance delivery.

## Current Deliverable

The current `main` branch can be reviewed as:

- RASHE offline scaffold for Retrieval-Augmented Skill Harness Evolution.
- Runtime behavior L1 approved only for `synthetic_default_disabled_only` wiring with defaults disabled.
- Fail-closed approval framework separating source/real-trace use, candidate/proposer execution, scorer execution, and performance/Huawei acceptance.
- Deterministic negative-evidence handoff showing that the prior Stage-1 deterministic repair search should not continue as mechanical family hunting.

## Current Non-Claims

The current `main` branch must not be described as:

- BFCL +3pp evidence.
- Huawei acceptance readiness.
- SOTA readiness or SOTA claim evidence.
- Candidate pool readiness.
- Scorer readiness or scorer authorization.
- Source collection authorization.
- Provider-call authorization.
- BFCL performance readiness.

## Gates Passed

The handoff is supported by these post-runtime fail-closed gates:

- Active evidence index route is RASHE.
- Runtime behavior approved checker passes for `synthetic_default_disabled_only`.
- After-runtime approval packet review matrix passes: runtime lane approved; four downstream lanes pending/fail-closed.
- Post-runtime main readiness checker passes.
- Artifact boundary checker passes.

Legacy pre-runtime gates remain available as historical/offline-scaffold checks, but they intentionally reject approved runtime packets and are not the current post-runtime gate.

## Still Forbidden

Until separate downstream approval packets are reviewed and signed, the following remain forbidden:

- Runtime enabled by default.
- Source collection or real-trace capture.
- Provider calls.
- Candidate/proposer execution.
- Candidate pool generation.
- BFCL scorer execution.
- Dev, holdout, or full BFCL runs.
- Performance, SOTA, +3pp, or Huawei acceptance claims.

## Recommended Next-Stage Order

The immediate next engineering step is synthetic/default-disabled runtime behavior tests only. After that, downstream approvals should proceed in this order if the project continues:

1. `source_real_trace_approval`
2. `candidate_proposer_execution_approval`
3. `scorer_dev_holdout_full_approval`
4. `performance_3pp_huawei_acceptance_approval`

Each lane must remain independently reviewed. Runtime L1 approval does not authorize any later lane.

## Files For External Review

When reviewers inspect the default `main` branch, use these files as the current handoff map:

- `outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_main_merge_readiness.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_approval_packet_review_matrix.json`
- `docs/stage1_rashe_handoff_summary.md`
- `docs/stage1_rashe_main_merge_readiness.md`
- `docs/stage1_rashe_approval_packet_review_matrix.md`
- `docs/stage1_bfcl_negative_evidence_report.md`
- `docs/stage1_bfcl_scope_change_decision_memo.md`

This package is ready for offline scaffold review and L1 synthetic/default-disabled runtime behavior testing only. Any source, provider, candidate, scorer, or performance work requires a separate downstream approval packet before execution.
