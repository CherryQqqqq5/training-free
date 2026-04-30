# Stage-1 RASHE Scope-Change Approval

RASHE (`retrieval_augmented_skill_harness_evolution`) is proposed as a possible Stage-1 BFCL scope-change route. It is not approved, not the active acceptance path, and not runtime behavior.

Current branch state remains diagnostic/negative-evidence handoff only:

- Provider technical preflight is green for Chuangzhi/Novacode `gpt-5.2`, but provider green is not scorer authorization.
- Deterministic Stage-1 family search is exhausted under current approved gates.
- `candidate_pool_ready=false`
- `scorer_authorization=false`
- `performance_evidence=false`
- `sota_3pp_claim_ready=false`
- `huawei_acceptance_ready=false`

## Proposed Route

RASHE would explore retrieval-augmented skill and harness evolution while preserving a training-free claim:

- skill packages / SkillBank
- deterministic skill router
- prompt/context injection
- local parser adapter
- bounded retry
- verification hook
- retrieval over sanitized step traces
- harness code under GRC runtime

These are proposed-only allowed change classes. No runtime implementation is authorized by this packet.


## Acceptance Fields

- provider_route: `Chuangzhi/Novacode`
- bfcl_eval_version: `bfcl-eval==2025.12.17`
- bfcl_protocol_id: `TBD_requires_approval`
- baseline_comparator_kind: `same_model_same_provider_baseline`
- hidden_model_calls_allowed: `false`
- suite_scope: `full_suite_or_signed_subset`
- subset_approval_id: `null` until signed
- dev_split_manifest: `null` until approved
- holdout_split_manifest: `null` until approved
- dev_holdout_disjoint: `false` while proposed

## Required Invariants

- `training_free_claim=true`
- `model_weights_changed=false`
- `bfcl_evaluator_modified=false`
- `same_model_same_provider_required=true`
- same provider/profile/model required for any future baseline/candidate comparison
- provider/profile/model: Chuangzhi/Novacode / `novacode` / `gpt-5.2`

## Forbidden Changes

- model weight updates
- BFCL evaluator modifications
- hidden gold/expected/reference use
- scorer diff used for skill generation
- holdout/full-suite feedback used for skill generation or thresholds
- provider/model drift between baseline and candidate
- case-id-specific rules or answer memorization
- candidate/scorer/performance claim before gates pass

## No-Leakage Requirements

- `gold_used=false`
- `expected_used=false`
- `scorer_diff_used_for_skill=false`
- `candidate_output_used_for_skill=false`
- `holdout_used_for_skill=false`
- `raw_trace_committed=false`

## Future Gate Requirements

Before any scorer can be requested, a separate approval must define:

- suite scope: full suite, or signed subset with subset approval id
- dev/holdout disjointness
- candidate pool gate
- paired comparison gate
- cost, latency, and regression gates

## Approval State

The corresponding compact artifact is `outputs/artifacts/stage1_bfcl_acceptance/scope_change_approval_rashe.json`. Its required status is `approval_status=proposed`; any future change to approved must be a separate signed decision and must not be inferred from this document.
