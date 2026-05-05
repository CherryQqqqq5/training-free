# Stage-1 BFCL Active Evidence Index

This index is the active evidence entrypoint for Stage-1 BFCL. It records current evidence and claim state only. It is not a BFCL performance claim, SOTA/+3pp claim, or Huawei acceptance claim.

## Current Checkpoint

- branch: `main`
- base_handoff_commit: `eaafa624`
- prior_post_runtime_cleanup_commit: `0ce63ba7d21620a39aa2eae8da8f4128c640e8aa`
- latest_committed_cleanup: `see git HEAD`
- main_merge_completed: true
- runtime_behavior_approval_status: `approved`
- runtime_behavior_scope: `synthetic_default_disabled_only`
- provenance note: commit fields above are non-self-referential anchors. The current cleanup commit is intentionally represented as `see git HEAD`.
- active route: `retrieval_augmented_skill_harness_evolution` (RASHE)
- RASHE route approved: true
- active route status: `rashe_offline_scaffold_complete_fail_closed_plus_l1_runtime_behavior_approved`
- no BFCL +3pp evidence yet: true

## Active Provider And Dataset Gates

- provider: Chuangzhi/Novacode
- profile: `novacode`
- model: `gpt-5.2`
- expected env: `NOVACODE_API_KEY`
- OpenRouter: disabled / excluded
- provider green technical preflight: true
- dataset/export gates: green from existing tracked evidence

Provider/dataset green status is technical preflight only. It does not authorize scorer, source collection, candidate generation, paired comparison, SOTA/+3pp, or Huawei acceptance claims.

## Runtime Approval Boundary

- offline_scaffold_alone_authorized_runtime_behavior: false
- runtime_behavior_approval_status: `approved`
- runtime_behavior_authorized: true
- runtime_behavior_scope: `synthetic_default_disabled_only`
- config default: `configs/runtime_bfcl_skills.yaml enabled=false`
- current post-runtime gate: `scripts/check_rashe_main_merge_readiness_after_runtime_behavior.py --compact --strict`
- legacy pre-runtime gate: `scripts/check_rashe_main_merge_readiness.py --compact --strict`

The legacy pre-runtime gate intentionally rejects approved runtime packets. The current post-runtime gate validates the approved L1 synthetic/default-disabled runtime behavior packet and keeps downstream lanes fail-closed.

## RASHE Offline Scaffold Gates

| gate | status | active evidence |
| --- | --- | --- |
| RASHE route approved | true | `outputs/artifacts/stage1_bfcl_acceptance/scope_change_approval_rashe.json` |
| runtime skeleton | `rashe_runtime_skeleton_passed=true` | `scripts/check_rashe_runtime_skeleton.py --compact --strict` |
| StepTraceBuffer | `rashe_step_trace_buffer_offline_passed=true` | `scripts/check_rashe_step_trace_buffer.py --compact --strict` |
| skill metadata/router | `rashe_skill_metadata_passed=true` | `scripts/check_rashe_skill_metadata.py --compact --strict` |
| proposer schema | `rashe_proposer_schema_passed=true` | `scripts/check_rashe_proposer_schema.py --compact --strict` |
| offline evolution loop | `rashe_offline_evolution_loop_passed=true` | `scripts/check_rashe_evolution_loop.py --compact --strict` |

Offline scaffold readiness remains evidence that the scaffold is present and fail-closed. It is not the source of runtime behavior authorization.

Active RASHE docs:

- `docs/stage1_rashe_skill_package_boundary.md`
- `docs/stage1_rashe_offline_evolution_loop.md`
- `docs/stage1_rashe_seed_skill_design.md`
- `docs/stage1_rashe_step_trace_buffer_design.md`
- `docs/stage1_rashe_v0_offline_skeleton_spec.md`
- `docs/stage1_rashe_runtime_implementation_plan.md`

## Active Diagnostic Evidence

| evidence | role | commit | status | artifact |
| --- | --- | --- | --- | --- |
| `bfcl_proxy_preflight_failure_telemetry_local_stub_approved_v2` | sanitized no-provider local-stub proxy preflight telemetry | `ee084cebe7a7c4a57b60f42cce6e76355ccd3b2a` | `active_diagnostic_only` | `outputs/artifacts/stage1_bfcl_acceptance/bfcl_proxy_preflight_failure_telemetry_local_stub_approved_v2_compact.json` |

This diagnostic evidence keeps provider, BFCL generate/evaluate, scorer, candidate, performance, and Huawei readiness lanes fail-closed. It is not BFCL performance evidence and does not change formal readiness.

## Readiness / Authorization

All formal BFCL performance gates remain fail-closed:

- runtime_behavior_authorized: true (`synthetic_default_disabled_only`; no real provider/source/scorer/candidate execution)
- source_collection_authorized: false
- candidate_generation_authorized: false
- candidate_pool_ready: false
- scorer_authorized: false
- performance_evidence: false
- sota_3pp_claim_ready: false
- huawei_acceptance_ready: false
- formal_bfcl_performance_ready: false

L1 runtime behavior approval does not authorize source expansion, BFCL scorer, candidate pool, dev/holdout split, paired comparison, full-suite run, SOTA/+3pp claim, or Huawei acceptance claim.

## Next Action

`prepare_downstream_approvals_before_source_candidate_scorer_performance`

The current approval state allows only L1 synthetic/default-disabled runtime behavior checks. Source collection, candidate generation, scorer, performance evidence, SOTA/+3pp claims, and Huawei acceptance remain separate pending lanes.
