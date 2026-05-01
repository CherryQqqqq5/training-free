# Stage-1 RASHE Main Merge Readiness

This report records post-runtime-approval consistency for the RASHE handoff on `main`; current follow-on source artifacts approve only bounded compact source diagnostics and have not executed collection. It is not BFCL performance readiness and does not authorize raw trace capture, raw payload tracking, candidate generation, scorer use, SOTA/+3pp claims, or Huawei acceptance readiness.

## Claim Scope

- main_merge_claim_scope: `post_runtime_l1_synthetic_default_disabled_only`
- runtime_behavior_approval_status: `approved`
- runtime_behavior_scope: `synthetic_default_disabled_only`
- bfcl_performance_ready: `false`
- sota_3pp_claim_ready: `false`
- huawei_acceptance_ready: `false`
- candidate_pool_ready: `false`
- scorer_authorized: `false`

## Required Gates

- Runtime behavior approved checker passes.
- Approved-source checker passes.
- After-source approval review matrix checker passes.
- Active evidence index is post-runtime consistent and non-self-referential.
- Runtime L1 approved; source lane approved only for bounded compact diagnostics; candidate/scorer/performance/Huawei lanes remain pending/fail-closed.
- Artifact boundary passes.
- Handoff docs and approval matrix docs are present.

The legacy `scripts/check_rashe_main_merge_readiness.py` is a pre-runtime/offline-scaffold gate. It intentionally rejects approved runtime packets and is not the current post-runtime gate.

## Required Commands

```bash
.venv/bin/python scripts/check_rashe_source_real_trace_approved.py --compact --strict
.venv/bin/python scripts/check_rashe_approval_packet_review_matrix_after_source_approval.py --compact --strict
.venv/bin/python scripts/check_rashe_runtime_behavior_approved.py --compact --strict
.venv/bin/python scripts/check_artifact_boundary.py
```

## Non-Claims

This handoff contains L1 synthetic/default-disabled runtime behavior approval plus source-lane approval only for bounded compact diagnostics; source collection has not been executed. It contains no raw trace/raw payload capture authorization, no candidate pool readiness, no scorer authorization, no BFCL +3pp evidence, and no Huawei acceptance claim.
