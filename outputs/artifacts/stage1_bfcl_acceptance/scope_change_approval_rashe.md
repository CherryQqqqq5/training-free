# RASHE Scope-Change Approval Packet

Status: `proposed`, not approved. This artifact does not authorize runtime implementation, source collection, candidate generation, scorer execution, paired comparison, SOTA/+3pp, or Huawei acceptance claims.

## Route

- report_scope: `scope_change_approval_rashe`
- scope_change_route: `retrieval_augmented_skill_harness_evolution`
- short_name: `RASHE`
- approval_status: `proposed`
- provider/profile/model: Chuangzhi/Novacode / `novacode` / `gpt-5.2`

Provider technical preflight is green, but provider green is not scorer authorization. Deterministic Stage-1 family search is exhausted under current approved gates.

## Fail-Closed Flags

- approved_before_implementation: `false`
- approved_before_source_collection: `false`
- approved_before_candidate_generation: `false`
- approved_before_scorer: `false`
- candidate_pool_ready: `false`
- scorer_authorization: `false`
- performance_evidence: `false`
- sota_3pp_claim_ready: `false`
- huawei_acceptance_ready: `false`

## Proposed-Only Allowed Changes

- skill packages / SkillBank
- deterministic skill router
- prompt/context injection
- local parser adapter
- bounded retry
- verification hook
- retrieval over sanitized step traces
- harness code under GRC runtime

## Forbidden Changes

- model weight updates
- BFCL evaluator modifications
- hidden gold/expected/reference use
- scorer diff used for skill generation
- holdout/full-suite feedback used for skill generation or thresholds
- provider/model drift between baseline and candidate
- case-id-specific rules or answer memorization
- candidate/scorer/performance claim before gates pass

## No-Leakage Fields

- gold_used: `false`
- expected_used: `false`
- scorer_diff_used_for_skill: `false`
- candidate_output_used_for_skill: `false`
- holdout_used_for_skill: `false`
- raw_trace_committed: `false`

## Gates Required Before Any Future Scorer

- suite scope must be full suite or a signed subset with subset approval id
- dev/holdout disjointness required before scorer
- candidate pool gate required
- paired comparison required
- cost, latency, and regression gates required

## Decision Boundary

RASHE is a proposed scope-change packet only. Project lead and Huawei acceptance owner must explicitly approve it before any implementation, source collection, candidate generation, scorer, or performance claim.
