# RASHE Runtime Implementation Authorization

Status: `proposed`, not approved. This packet requests future runtime implementation authorization only; it does not authorize implementation, provider calls, source collection, scorer execution, candidate generation, dev/holdout manifests, BFCL runtime prompt injection, SOTA/+3pp, or Huawei acceptance claims.

## Fail-Closed Flags

- runtime_implementation_authorized: `false`
- provider_calls_authorized: `false`
- source_collection_authorized: `false`
- scorer_authorized: `false`
- candidate_generation_authorized: `false`
- performance_evidence: `false`
- active_acceptance_path: `false`
- candidate_pool_ready: `false`
- default_enabled: `false`

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

This packet is intentionally fail-closed. A separate approval must flip `runtime_implementation_authorized=true` before any runtime code path is implemented or enabled.
