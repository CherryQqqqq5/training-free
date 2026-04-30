# RASHE Runtime Implementation Authorization

Status: `approved` for default-disabled inert runtime skeleton implementation only. This packet does not authorize runtime behavior activation, provider calls, source collection, scorer execution, candidate generation, dev/holdout manifests, BFCL runtime prompt injection, SOTA/+3pp, or Huawei acceptance claims.

## Runtime Skeleton Authorization

- authorization_status: `approved`
- runtime_implementation_scope: `default_disabled_inert_skeleton_only`
- runtime_behavior_authorized: `false`

## Fail-Closed Flags

- runtime_implementation_authorized: `true`
- provider_calls_authorized: `false`
- source_collection_authorized: `false`
- scorer_authorized: `false`
- candidate_generation_authorized: `false`
- performance_evidence: `false`
- active_acceptance_path: `false`
- candidate_pool_ready: `false`
- default_enabled: `false`


## Design Constraints

Raman/Schrodinger conditions for this approval:

- do not import RuleEngine/proxy active path
- do not activate prompt injection
- do not implement retry behavior
- do not call provider/scorer/source collection
- do not create candidate JSONL/dev/holdout manifests
- do not use gold/expected/scorer diff
- do not use raw case_id/raw trace
- config must remain `enabled=false` by default

## Allowed Future Implementation Scope After Approval

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

## Gates Before Runtime Implementation Authorization Can Flip True

- v0 offline checker passed
- no-leakage policy passed
- seed skills validated
- router ambiguity fail-closed
- config default disabled
- code change plan reviewed
- no provider/scorer/source paths touched

This packet is intentionally fail-closed for behavior. Runtime skeleton files may be implemented only as default-disabled and inert. A separate execution approval is required before any runtime path is imported, enabled, or connected to provider/source/scorer/candidate flows.
