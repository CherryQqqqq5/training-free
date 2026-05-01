# Stage-1 RASHE Main Merge Readiness

This report records post-runtime-approval consistency for the RASHE handoff on `main`. It is not BFCL performance readiness and does not authorize provider calls, source collection, candidate generation, scorer use, SOTA/+3pp claims, or Huawei acceptance readiness.

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
- After-runtime behavior review matrix checker passes.
- Active evidence index is post-runtime consistent and non-self-referential.
- Runtime L1 approved; four downstream lanes remain pending/fail-closed.
- Artifact boundary passes.
- Handoff docs and approval matrix docs are present.

The legacy `scripts/check_rashe_main_merge_readiness.py` is a pre-runtime/offline-scaffold gate. It intentionally rejects approved runtime packets and is not the current post-runtime gate.

## Required Commands

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_rashe_main_merge_readiness_after_runtime_behavior.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_rashe_runtime_behavior_approved.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_rashe_approval_packet_review_matrix_after_runtime_behavior.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
```

## Non-Claims

This handoff contains L1 synthetic/default-disabled runtime behavior approval only. It contains no source collection authorization, no candidate pool readiness, no scorer authorization, no BFCL +3pp evidence, and no Huawei acceptance claim.
