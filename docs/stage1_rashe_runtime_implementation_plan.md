# Stage-1 RASHE Runtime Implementation Plan

This is a proposed implementation plan, not authorization to implement runtime behavior. Current authorization status is recorded in `outputs/artifacts/stage1_bfcl_acceptance/rashe_runtime_implementation_authorization.json`.

## Current State

- RASHE scope-change route is approved.
- RASHE v0 offline skeleton is present and disabled.
- Runtime implementation authorization is proposed, not approved.
- No provider/scorer/source/candidate/dev-holdout/runtime behavior is authorized by this plan.

## Proposed Files After Approval

- `src/grc/skills/schema.py`
- `src/grc/skills/store.py`
- `src/grc/skills/router.py`
- `src/grc/skills/verifier.py`
- `configs/runtime_bfcl_skills.yaml` with `enabled=false` by default
- synthetic tests only initially

## Forbidden Until Later Execution Approval

- RuleEngine/proxy behavior change
- provider calls
- BFCL scorer
- source collection
- candidate JSONL/dev/holdout manifests
- skill extraction from BFCL eval cases
- prompt injection active in BFCL runtime

## Required Gates

The runtime implementation authorization may flip true only after:

- `scripts/check_rashe_v0_offline.py --compact --strict` passes
- no-leakage policy passes
- seed skills validate
- router ambiguity fails closed
- config defaults remain disabled
- code change plan is reviewed
- no provider/scorer/source paths are touched

Even after runtime implementation authorization, execution approvals for provider calls, source collection, candidate generation, scorer, and performance evidence remain separate gates.
