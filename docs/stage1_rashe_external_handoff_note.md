# Stage-1 RASHE External Handoff Note

This note is the external-facing handoff scope for the current `main` branch after the Stage-1 RASHE merge. It is a fail-closed offline scaffold delivery, not a BFCL performance delivery.

## Current Deliverable

The current `main` branch can be reviewed as:

- RASHE offline scaffold for Retrieval-Augmented Skill Harness Evolution.
- Fail-closed approval framework separating runtime behavior, source/real-trace use, candidate/proposer execution, scorer execution, and performance/Huawei acceptance.
- Deterministic negative-evidence handoff showing that the prior Stage-1 deterministic repair search should not continue as mechanical family hunting.

## Current Non-Claims

The current `main` branch must not be described as:

- BFCL +3pp evidence.
- Huawei acceptance readiness.
- SOTA readiness or SOTA claim evidence.
- Candidate pool readiness.
- Scorer readiness or scorer authorization.
- BFCL performance readiness.

## Gates Passed

The handoff is supported by these fail-closed gates:

- Active evidence index route is RASHE offline scaffold.
- RASHE offline scaffold readiness checker passes.
- Approval packets remain pending and fail-closed.
- Approval packet review matrix passes.
- Main merge readiness checker passes for `offline_scaffold_only` scope.
- Artifact boundary checker passes.

## Still Forbidden

Until separate approval packets are reviewed and signed, the following remain forbidden:

- Runtime behavior enablement.
- Source collection or real-trace capture.
- Candidate/proposer execution.
- Candidate pool generation.
- BFCL scorer execution.
- Dev, holdout, or full BFCL runs.
- Performance, SOTA, +3pp, or Huawei acceptance claims.

## Recommended Next-Stage Order

If the project continues beyond the offline scaffold handoff, approvals should proceed in this order:

1. `runtime_behavior_approval`
2. `source_real_trace_approval`
3. `candidate_proposer_execution_approval`
4. `scorer_dev_holdout_full_approval`
5. `performance_3pp_huawei_acceptance_approval`

Each lane must remain independently reviewed. Approval of an earlier lane does not authorize later lanes.

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

This package is ready for offline scaffold review only. Any runtime, source, candidate, scorer, or performance work requires a separate approval packet before execution.
