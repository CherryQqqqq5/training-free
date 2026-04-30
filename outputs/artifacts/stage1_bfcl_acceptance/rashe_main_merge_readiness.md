# RASHE Main Merge Readiness

This report checks whether `stage1-bfcl-performance-sprint` is suitable to merge as a fail-closed RASHE offline scaffold branch. It is not BFCL performance readiness and does not authorize runtime behavior, source collection, candidate generation, scorer use, SOTA/+3pp claims, or Huawei acceptance readiness.

## Claim Scope

- main_merge_claim_scope: `offline_scaffold_only`
- bfcl_performance_ready: `false`
- sota_3pp_claim_ready: `false`
- huawei_acceptance_ready: `false`
- candidate_pool_ready: `false`
- scorer_authorized: `false`

## Required Gates

- Active evidence index route is RASHE offline scaffold.
- RASHE offline scaffold readiness checker passes.
- Approval packet review matrix checker passes.
- Approval packet checker confirms all five packets remain pending/fail-closed.
- Artifact boundary passes.
- Deterministic negative evidence / handoff summary is present.
- Handoff docs and approval matrix docs are present.

## Required Commands

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_rashe_main_merge_readiness.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_rashe_approval_packet_review_matrix.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_rashe_offline_scaffold_ready.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
```

## Non-Claims

This branch remains a diagnostic/offline scaffold handoff. It contains no BFCL +3pp evidence, no candidate pool readiness, no scorer authorization, and no Huawei acceptance claim.
