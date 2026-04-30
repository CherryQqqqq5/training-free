# Stage-1 BFCL Active Evidence Index

This index is the active evidence entrypoint for Stage-1 BFCL. It records current evidence and claim state only. It is not a BFCL performance claim, SOTA/+3pp claim, or Huawei acceptance claim.

## Current Checkpoint

- source branch: `stage1-bfcl-performance-sprint`
- current_head: `e7679431`
- artifact_commit: `e7679431`
- provenance note: these fields record the latest pushed evidence commit available at refresh start. The containing refresh commit is available from git history/final handoff; the index does not make a recursive hash claim.
- active route: `retrieval_augmented_skill_harness_evolution` (RASHE)
- RASHE route approved: true
- active route status: `rashe_offline_scaffold_complete_fail_closed`
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

## RASHE Offline Scaffold Gates

| gate | status | active evidence |
| --- | --- | --- |
| RASHE route approved | true | `outputs/artifacts/stage1_bfcl_acceptance/scope_change_approval_rashe.json` |
| runtime skeleton | `rashe_runtime_skeleton_passed=true` | `scripts/check_rashe_runtime_skeleton.py --compact --strict` |
| StepTraceBuffer | `rashe_step_trace_buffer_offline_passed=true` | `scripts/check_rashe_step_trace_buffer.py --compact --strict` |
| skill metadata/router | `rashe_skill_metadata_passed=true` | `scripts/check_rashe_skill_metadata.py --compact --strict` |
| proposer schema | `rashe_proposer_schema_passed=true` | `scripts/check_rashe_proposer_schema.py --compact --strict` |
| offline evolution loop | `rashe_offline_evolution_loop_passed=true` | `scripts/check_rashe_evolution_loop.py --compact --strict` |

Active RASHE artifact paths:

- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/skill.schema.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/step_trace.schema.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/router_decision.schema.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/verifier_report.schema.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/proposal_draft.schema.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/evolution_loop.schema.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/skillbank_manifest.json`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/seed_skills/`
- `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/fixtures/`

Active RASHE docs:

- `docs/stage1_rashe_skill_package_boundary.md`
- `docs/stage1_rashe_offline_evolution_loop.md`
- `docs/stage1_rashe_seed_skill_design.md`
- `docs/stage1_rashe_step_trace_buffer_design.md`
- `docs/stage1_rashe_v0_offline_skeleton_spec.md`
- `docs/stage1_rashe_runtime_implementation_plan.md`

## Readiness / Authorization

All formal BFCL performance gates remain fail-closed:

- candidate_pool_ready: false
- candidate_generation_authorized: false
- runtime_behavior_authorized: false
- source_collection_authorized: false
- scorer_authorized: false
- performance_evidence: false
- sota_3pp_claim_ready: false
- huawei_acceptance_ready: false
- formal_bfcl_performance_ready: false

No source expansion, BFCL scorer, candidate pool, dev/holdout split, paired comparison, full-suite run, SOTA/+3pp claim, or Huawei acceptance claim is authorized by the RASHE offline scaffold.

## Next Action

`build_rashe_readiness_checker_or_prepare_separate_approvals_before_runtime_source_candidate_scorer`

The next engineering step is a RASHE readiness checker or separate approval packets before any runtime behavior, source collection, candidate generation, scorer, or performance evidence path can start.

## Historical Background

The prior deterministic Stage-1 family search remains background negative evidence:

- explicit required-arg literal: zero accepted under selected-call diagnostics
- wrong-key alias repair: zero eligible
- schema-local non-live repair: zero eligible
- structural malformed/final-before-tool attribution: zero eligible
- raw tool-name/schema normalization: zero yield
- schema retrieval/rerank feasibility: zero yield

These negative diagnostics explain why the active route moved to RASHE offline scaffold. They are not performance evidence and do not authorize candidate promotion.

## Excluded / Superseded Evidence

- `outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.md`: superseded markdown with old 401/OpenRouter wording; active provider evidence is `provider_green_preflight.{json,md}` plus `current_provider_preflight_status.json`.
- historical provider unblock/failure artifacts: excluded from active claim.
- old CTSPC subset/candidate/dev20 artifacts: excluded from active Stage-1 claim.
- Phase-2 memory/postcondition artifacts: excluded from Stage-1 BFCL +3pp evidence.
- any OpenRouter, old 401, or gpt-5.4 provider/source status references: superseded by Chuangzhi/Novacode gpt-5.2 route.

## Provenance Table

| artifact_path | evidence_role | source_code_head | artifact_commit | route/model | active/superseded |
| --- | --- | --- | --- | --- | --- |
| `outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.json` | technical provider preflight green only | `d39a954d` | `d39a954d` | Chuangzhi/Novacode gpt-5.2 | active |
| `outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json` | canonical provider preflight status JSON | `d39a954d` | `d39a954d` | Chuangzhi/Novacode gpt-5.2 | active |
| `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/skillbank_manifest.json` | RASHE seed skillbank manifest; offline scaffold only | `a101b74a/b32be30b/ebd842eb` | `e7679431` | offline synthetic only; no provider/scorer | active |
| `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/step_trace.schema.json` | RASHE StepTrace v0.2 schema; offline only | `b32be30b` | `e7679431` | offline synthetic/approved_compact only | active |
| `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/proposal_draft.schema.json` | RASHE inert proposal draft schema; no candidate generation | `ce7960dd` | `e7679431` | offline synthetic only | active |
| `outputs/artifacts/stage1_bfcl_acceptance/rashe_v0/evolution_loop.schema.json` | RASHE offline evolution loop schema; inert metadata patch planning only | `e7679431` | `e7679431` | offline synthetic only | active |
| `outputs/artifacts/stage1_bfcl_acceptance/baseline_only_scored_failure_taxonomy_audit.json` | aggregate scored failure taxonomy; not performance evidence | `f1fa5507/d48e6211` | `d48e6211` | Chuangzhi/Novacode gpt-5.2 source metadata | background |
| `outputs/artifacts/stage1_bfcl_acceptance/schema_retrieval_rerank_feasibility_diagnostic.json` | schema retrieval/rerank feasibility; zero-yield | `a19f74c4` | `a19f74c4` | offline existing raw pilot only; no provider/scorer | background |
