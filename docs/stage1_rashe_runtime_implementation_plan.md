# Stage-1 RASHE Runtime Implementation Plan

This plan records the approved default-disabled runtime implementation skeleton and the L1 synthetic/default-disabled runtime behavior boundary. It does not authorize provider calls, source collection, candidate generation, scorer execution, performance evidence, or Huawei acceptance claims.

## Current State

- RASHE scope-change route is approved.
- RASHE v0 offline skeleton is present and disabled.
- Runtime implementation skeleton is approved only for default-disabled inert files.
- L1 runtime behavior is approved only for synthetic/default-disabled wiring.

## Implemented / Allowed Files Under Skeleton Approval

- `src/grc/skills/schema.py`
- `src/grc/skills/store.py`
- `src/grc/skills/router.py`
- `src/grc/skills/verifier.py`
- `configs/runtime_bfcl_skills.yaml` with `enabled=false` by default
- synthetic tests only initially

## Still Forbidden Without Later Execution Approval

- RuleEngine/proxy behavior change
- provider calls
- BFCL scorer
- source collection
- candidate JSONL/dev/holdout manifests
- skill extraction from BFCL eval cases
- prompt injection active in BFCL runtime

## Required Gates

Runtime implementation skeleton approval has already been granted for default-disabled inert files. L1 runtime behavior approval is synthetic/default-disabled only and still requires:

- config defaults remain disabled
- router ambiguity fails closed
- synthetic tests only
- no provider/scorer/source/candidate paths are touched
- no prompt injection or retry in real BFCL runtime

Source collection, provider calls, candidate generation, scorer execution, performance evidence, SOTA/+3pp claims, and Huawei acceptance remain pending and unauthorized separate gates.
