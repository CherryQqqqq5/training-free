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
- active route: `archive_based_behavior_harness_evolution` (ABHE)
- predecessor route: `retrieval_augmented_skill_harness_evolution` (RASHE discovery scaffold)
- RASHE route retained as predecessor: true
- active route status: `abhe_planning_archive_policy_fail_closed`
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

## ABHE Planning Route

ABHE is the active planning route. It is archive-based and behavior-level:

- archive: `abhe_archive/archive_index.json`
- opportunity table: `abhe_archive/opportunity_table.json`
- policy config: `abhe_archive/policy_config.yaml`
- ABHE-v0 behavior taxonomy: `abhe_archive/behavior_taxonomy_v0.json`
- planner: `scripts/plan_abhe_next_evolution.py --write --compact --strict`
- planner output: `outputs/artifacts/stage1_bfcl_acceptance/abhe_next_evolution_plan.json`
- ABHE-v0 simple closed-loop doc: `docs/stage1_abhe_v0_simple_closed_loop.md`
- ABHE-v0 policy score: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_policy_score.json`
- ABHE-v0 simple candidate specs: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_simple_candidate_specs.json`
- ABHE-v0 synthetic fresh dev slice manifest: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_synthetic_fresh_dev_slice_manifest.json`
- ABHE-v0 synthetic dev feedback: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_synthetic_dev_feedback.json`
- ABHE-v0 archive transition plan: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_archive_transition_plan.json`
- ABHE-v0 BFCL fresh dev slice plan: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_plan.json`
- ABHE-v0 BFCL dataset path review: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dataset_path_review.json`
- ABHE-v0 BFCL category review: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_category_review.json`
- ABHE-v0 BFCL fresh dev slice review: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_fresh_dev_slice_review.json`
- ABHE-v0 BFCL source exclusion proof: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_source_exclusion_proof.json`
- ABHE-v0 BFCL fresh slice review memo: `docs/stage1_abhe_v0_bfcl_fresh_slice_review_memo.md`
- ABHE-v0 candidate materialization plan: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_candidate_materialization_plan.json`
- ABHE-v0 BFCL dev smoke approval request: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_approval_request.json`
- ABHE-v0 BFCL execution readiness: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_execution_readiness.json`
- ABHE-v0 BFCL dry-run manifest: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_smoke_dry_run_manifest.json`
- ABHE-v0 BFCL compact dev feedback schema: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_dev_feedback.schema.json`
- ABHE-v0 BFCL archive transition plan: `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_bfcl_archive_transition_plan.json`
- planning readiness: `outputs/artifacts/stage1_bfcl_acceptance/abhe_planning_ready.json`
- review bundle: `outputs/artifacts/stage1_bfcl_acceptance/abhe_review_bundle.json`
- approval chain: `outputs/artifacts/stage1_bfcl_acceptance/abhe_approval_chain.json`
- granular approval review memo: `docs/stage1_abhe_granular_approval_review_memo.md`
- review request: `outputs/artifacts/stage1_bfcl_acceptance/abhe_review_request.json`
- execution approval schema: `outputs/artifacts/stage1_bfcl_acceptance/abhe_execution_approval.schema.json`
- trace extraction approval schema: `outputs/artifacts/stage1_bfcl_acceptance/abhe_trace_extraction_approval.schema.json`
- fresh dev slice approval schema: `outputs/artifacts/stage1_bfcl_acceptance/abhe_fresh_dev_slice_approval.schema.json`
- candidate spec approval schema: `outputs/artifacts/stage1_bfcl_acceptance/abhe_candidate_spec_approval.schema.json`
- fresh dev slice request: `outputs/artifacts/stage1_bfcl_acceptance/abhe_fresh_dev_slice_request.json`
- execution readiness: `outputs/artifacts/stage1_bfcl_acceptance/abhe_execution_readiness.json`
- candidate spec drafts: `docs/stage1_abhe_state_tracking_candidate_spec_draft.md`, `docs/stage1_abhe_hallucination_abstain_candidate_spec_draft.md`
- post-dev synthetic fixtures: `tests/fixtures/abhe_dev_feedback/`
- state transition dry-run skeleton: `scripts/append_abhe_state_transition.py`

The ABHE planner does not call a provider, run BFCL/model code, authorize scorer, generate candidates, or claim performance. It only chooses which archive entries should request a future fresh bounded dev smoke packet.

Current ABHE decision:

- `state_tracking_v0`: request bounded dev smoke.
- `hallucination_abstain_v0`: request bounded dev smoke.
- `unresolved_search_memory_watch_v0`: watch; split or collect more compact diagnostics.

The 160 compact source cases are discovery/archive-seeding evidence only. They are not candidate validation or improvement evidence.

Current execution state: ABHE planning readiness, approval-chain review bundle readiness, the granular approval review memo, and the ABHE-v0 synthetic closed-loop baseline are ready for human review, but execution readiness is false. The dry-run-only runner is materialized for manifest checks; trace extraction approval, fresh dev slice approval, candidate spec approval, execution approval, candidate rule, runtime config, scorer authorization, and performance evidence remain absent/fail-closed.

ABHE-v0 synthetic closed-loop status:

- taxonomy entries: 10 two-level behavior clusters
- selected synthetic top-2 entries: `state_tracking_v0`, `hallucination_abstain_v0`
- candidate specs: non-executable spec artifacts only
- synthetic feedback: fixture-only, paired dev smoke not executed
- archive transition plan: dry-run only, archive not updated
- performance evidence: false

ABHE-v0 BFCL dev smoke gate status:

- fresh BFCL dev slice plan: present, not materialized
- dataset path review: present, selected path pending reviewer selection
- category review: present, proposed top-2 strata only
- source exclusion proof: blocked until dataset path selection; discovery compact source count is 160
- selected case list hash: pending until reviewer-selected dataset path and materialization
- candidate materialization plan: present, no candidate rule/YAML/JSONL generated
- dev smoke approval request: pending and not authorized
- dry-run runner manifest: present; provider, BFCL generate/evaluate, and scorer flags are false
- execution readiness: false
- archive transition plan: dry-run only, archive not updated
- performance evidence: false

## RASHE Predecessor Scaffold Gates

| gate | status | active evidence |
| --- | --- | --- |
| RASHE route approved | true | `outputs/artifacts/stage1_bfcl_acceptance/scope_change_approval_rashe.json` |
| runtime skeleton | `rashe_runtime_skeleton_passed=true` | `scripts/check_rashe_runtime_skeleton.py --compact --strict` |
| StepTraceBuffer | `rashe_step_trace_buffer_offline_passed=true` | `scripts/check_rashe_step_trace_buffer.py --compact --strict` |
| skill metadata/router | `rashe_skill_metadata_passed=true` | `scripts/check_rashe_skill_metadata.py --compact --strict` |
| proposer schema | `rashe_proposer_schema_passed=true` | `scripts/check_rashe_proposer_schema.py --compact --strict` |
| offline evolution loop | `rashe_offline_evolution_loop_passed=true` | `scripts/check_rashe_evolution_loop.py --compact --strict` |

Offline scaffold readiness remains evidence that the scaffold is present and fail-closed. It is not the active complete method, not a direct scorer route, and not the source of performance evidence.

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

`review_select_bfcl_dataset_path`

ABHE-v0 synthetic closed-loop baseline is ready for human review; RASHE remains discovery predecessor. Trace extraction, fresh dev slice, candidate spec review, and bounded dev smoke execution each require separate approved packets. Source collection, candidate generation, scorer, real fresh dev slice materialization, archive mutation, performance evidence, SOTA/+3pp claims, and Huawei acceptance remain pending/fail-closed.
