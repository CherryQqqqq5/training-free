# Stage-1 Huawei Acceptance Approval Template

This document is the approval template for the formal Stage-1 BFCL performance
acceptance path. It is not a scaffold handoff note and it does not authorize
scorer execution by itself.

Current repository state is fail-closed:

- Formal BFCL performance acceptance: `not ready`
- Provider technical preflight: green for Chuangzhi/Novacode `gpt-5.2`
- Provider green is not scorer authorization
- Current blocker: `deterministic_stage1_family_search_exhausted`
- Next action: `negative_evidence_report_or_scope_change_review`
- Candidate pool ready: `false`
- Scorer authorized: `false`
- Performance evidence: `false`
- Huawei acceptance ready: `false`
- Allowed claim today: diagnostic/negative-evidence handoff only

Historical note: earlier provider HTTP `401` / provider-green-not-passed wording is
superseded by the Chuangzhi/Novacode technical preflight. It remains relevant
only as a generic hard-fail condition if it recurs.

Related provider unblock documents:

```text
docs/stage1_provider_access_request.md
docs/stage1_acceptance_state_machine.md
outputs/artifacts/stage1_bfcl_acceptance/provider_unblock_request.md
```

## 1. Provider Green Artifact

The approval package must archive compact provider evidence before any source
collection or scorer run.

Required artifacts:

```text
outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.json
outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.md
outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json
<baseline_or_candidate_run>/artifacts/preflight_report.json
scripts/check_provider_green_preflight.py --compact --strict
scripts/check_artifact_boundary.py
```

The old `outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.md` is superseded unless regenerated from current green evidence; it is not active required provider evidence.

Required provider fields:

```text
provider_profile
provider_approval_id
expected_api_key_env
credential_present = true
credential_value_logged = false
base_url = sanitized
upstream_model_route
bfcl_model_alias
runtime_config_path
upstream_auth_passed = true
model_route_available = true
bfcl_compatible_response = true
source_collection_rerun_ready = true
candidate_evaluation_ready = true
chat_tool_call = pass
responses_tool_call = pass
chat_text_response = pass
trace_emission = pass
provider_green_preflight_passed = true
```

Hard fail rules:

- Any unresolved HTTP `401` or `403`.
- Provider/model route differs between baseline and candidate.
- Tool-call, text-response, or trace-emission preflight fails.
- Provider credential value, raw provider response, `.env`, raw BFCL result tree,
  trace tree, logs, or repair records appear in the committed delivery package.

## 2. SOTA or Baseline Freeze

The SOTA or accepted baseline comparator must be frozen before scorer execution.
If Huawei does not provide an external SOTA snapshot, the enforceable comparator
is the same-model, same-provider, same-protocol accepted baseline.

Required frozen fields:

```text
comparison_kind = external_sota | accepted_same_protocol_baseline
freeze_timestamp_utc
frozen_before_scorer = true
approval_id
benchmark = BFCL
bfcl_eval_version
bfcl_checkout
suite_scope = full_suite | category | dev20 | holdout20
test_category
provider_profile
upstream_model_route
bfcl_model_alias
runtime_config_path
same_scale_definition
baseline_or_sota_source
baseline_accuracy
calculation_unit = absolute_pp
required_delta_pp = 3.0
```

Hard fail rules:

- Any required comparator field is `TBD`, empty, or frozen after scorer output is
  known.
- External SOTA lacks source, date, BFCL version, model, provider, or score.
- Candidate is compared against a different provider/model/protocol without
  explicit Huawei approval.
- The `+3` calculation unit is ambiguous.

## 3. Scorer Authorization Request

This section must be filled before baseline/candidate scorer commands are run.

```text
request_id:
requester:
approval_owner:
approval_timestamp_utc:
provider_profile:
provider_approval_id:
upstream_model_route:
bfcl_model_alias:
bfcl_eval_version:
bfcl_checkout:
protocol_id:
runtime_config_path:
benchmark_scope:
test_category:
selected_case_ids_sha256:
baseline_rules_dir:
candidate_rules_dir:
candidate_rules_snapshot_sha256:
scope_change_route: none | schema_parser_feedback_retry | verifier_test_time_repair | prompt_context_canonicalization | training_data_route | retrieval_augmented_skill_harness_evolution
scope_change_approval_id:
scope_change_approval_owner:
scope_change_approved_before_execution: false
deterministic_family_search_exhausted: true
candidate_pool_ready: false
scorer_authorization_ready: false
performance_evidence: false
no_leakage_check_passed:
dev20_manifest_ready:
holdout20_manifest_ready:
dev_holdout_disjoint:
manifest_case_integrity_passed:
m2_8pre_offline_passed:
sota_or_acceptance_baseline_frozen_before_scorer:
planned_baseline_command:
planned_candidate_command:
raw_artifact_storage_location:
compact_artifact_output_location:
rollback_plan:
```

Minimum approval conditions:

- `provider_green_preflight_passed=true`
- `artifact_boundary_passed=true`
- `scope_change_route != none`
- `scope_change_approval_id` is recorded
- `scope_change_approval_owner` is recorded
- `scope_change_approved_before_execution=true`
- `deterministic_family_search_exhausted=true` is acknowledged
- candidate pool readiness may be true only after a newly approved scope-change candidate pool passes its own gate
- `scorer_authorization_ready=true` only after candidate pool, split, no-leakage, and protocol gates pass
- `performance_evidence=false` until paired baseline/candidate scorer artifacts exist
- `m2_8pre_offline_passed=true` or a replacement scope-change offline gate is explicitly approved
- `no_leakage_check_passed=true`
- `dev_holdout_disjoint=true`
- `manifest_case_integrity_passed=true`
- SOTA or accepted baseline comparator is frozen before scorer execution

Historical / unauthorized explicit-literal route:

- `candidate_family=explicit_required_arg_literal_completion` and
  `explicit_literal_candidate_pool_passed=true` were historical route-specific
  approval fields.
- This route is now zero-yield under approved gates and is not the active current
  approval path.
- Do not require or cite explicit-literal-specific candidate counts as current
  scorer authorization fields unless a new scope-change approval explicitly
  reselects that route.

No-leakage requirements:

- Candidate rules may use only schema-local, current-request, or current
  observation evidence.
- Candidate rules must not use scorer gold, hidden source results, case ids,
  target labels, raw scorer feedback, or post-hoc scorer outcomes as trigger or
  argument sources.
- Candidate rules must not change provider, model, evaluator, BFCL tool schema,
  trajectory order, or tool choice unless separately approved.

## 4. Authorization Gate Sequence

Each gate requires a separate recorded approval. Passing an earlier gate does not
authorize a later gate.

Command packs are separated into three classes:

```text
provider_source_collection_command_pack:
  allowed only after provider credential, dataset export, and source collection
  approvals; never authorizes scorer.
dev_holdout_scorer_command_pack:
  allowed only after source collection, candidate pool promotion, and the
  relevant dev/holdout gate; never authorizes full BFCL or Huawei acceptance.
full_huawei_scorer_command_pack:
  allowed only after holdout passes and Huawei signs the full or narrowed
  acceptance scope.
```

### 4.1 Provider Credential Approval

Required before attempting provider green preflight:

```text
provider_profile:
expected_api_key_env: env var name only, no secret value
base_url:
upstream_model_route:
bfcl_model_alias:
runtime_config_path:
allowed_categories:
allowed_splits: provider_preflight, source_collection
allowed_full_suite: yes | no
max_requests:
max_input_tokens:
max_output_tokens:
request_timeout_seconds:
overall_timeout_minutes:
retry_policy:
rate_limit_policy:
provider_access_approval_owner:
credential_owner:
budget_owner:
huawei_acceptance_owner:
engineering_execution_owner:
provider_approval_id:
approval_timestamp_utc:
```

Provider credential approval permits provider green preflight only. It does not
authorize dataset export, source collection, candidate pool promotion, scorer
execution, or any performance claim.

### 4.2 BFCL Dataset Fixture/Export Approval

Required before exporting or using BFCL dataset fixtures for source collection
or extractor work:

```text
dataset_export_approval_owner:
huawei_acceptance_owner:
engineering_execution_owner:
bfcl_eval_version:
bfcl_checkout:
benchmark_scope: full_suite | category | dev20 | holdout20 | huawei_signed_scope
test_category:
dataset_source_path:
export_output_path:
export_record_count:
case_id_hash:
schema_hash:
same_bfcl_version_as_scorer = true
same_scope_as_scorer = true
gold_fields_excluded = true
score_fields_excluded = true
candidate_output_fields_excluded = true
hidden_target_fields_excluded = true
raw_scorer_feedback_excluded = true
artifact_boundary_passed = true
approval_timestamp_utc:
```

Dataset export approval permits only the signed dataset fixture/export operation
for the frozen BFCL version and scope. It must exclude gold, expected/reference,
score, candidate-output, hidden target, and raw scorer feedback fields. The
exported dataset fixture must use the same BFCL version and approved scope that
will be used by scorer. Dataset export approval does not authorize provider
calls, source collection, candidate pool promotion, scorer execution, or any
performance claim.

### 4.3 Source Collection Authorization

Required before running source collection commands:

```text
provider_green_preflight_passed = true
provider_unblock_signed = true
dataset_export_approval_signed = true
provider_profile = frozen
expected_api_key_env = frozen env var name only
base_url = frozen sanitized value
upstream_model_route = frozen
bfcl_model_alias = frozen
runtime_config_path = frozen
bfcl_eval_version = frozen
bfcl_checkout = frozen
benchmark_scope = frozen
test_category = frozen
case_id_hash = signed dataset export value
schema_hash = signed dataset export value
allowed_categories = signed list
allowed_splits = provider_preflight, source_collection
budget_timeout_policy_present = true
raw_diagnostics_storage_outside_deliverable_artifacts = true
compact_artifact_output_location = signed
source_collection_approval_owner:
huawei_acceptance_owner:
engineering_execution_owner:
approval_timestamp_utc:
```

Source collection authorization permits only the signed source collection
commands. It does not authorize candidate pool promotion, dev scorer, holdout
scorer, full BFCL scorer, paired comparison, or any performance claim.

### 4.3.1 Option A Scope-Change Approval Packet Fields

Required only if project lead and Huawei acceptance owner choose
`schema_parser_feedback_retry`. This packet does not authorize scorer execution
by itself.

```text
scope_change_route = schema_parser_feedback_retry
scope_change_approval_id:
scope_change_approval_owner:
scope_change_approved_before_execution: false
retry_trigger_policy_path:
feedback_template_hash:
allowed_trigger_classes:
gold_or_expected_used: false
scorer_diff_used: false
provider_call_delta_bound:
latency_delta_bound:
regression_gate_required: true
candidate_pool_ready: false
scorer_authorization_ready: false
performance_evidence: false
```

Hard fail rules:

- Any gold, expected, reference, possible-answer, scorer-diff, candidate-output,
  or repair-output field is used as trigger, value, or argument source.
- Trigger classes are fuzzy, semantic, model-generated, or tuned to the same
  pilot without a separate anti-overfitting approval.
- Provider calls, latency, or regression bounds are undefined before scorer
  authorization is requested.

### 4.4 Candidate Pool Promotion Authorization

Required before promoting extractor outputs to acceptance candidate-pool
evidence:

```text
source_collection_completed = true
source_manifests_signed = true
artifact_boundary_passed = true
scope_change_route = none | schema_parser_feedback_retry | verifier_test_time_repair | prompt_context_canonicalization | training_data_route | retrieval_augmented_skill_harness_evolution
scope_change_approval_id:
scope_change_approval_owner:
scope_change_approved_before_execution = false
deterministic_family_search_exhausted = true
candidate_pool_ready = false
scorer_authorization_ready = false
performance_evidence = false
new_route_candidate_pool_gate_passed = false
no_leakage_check_passed = true
dev20_manifest_ready = true
holdout20_manifest_ready = true
dev_holdout_disjoint = true
manifest_case_integrity_passed = true
candidate_pool_approval_owner:
huawei_acceptance_owner:
approval_timestamp_utc:
```

Candidate pool promotion does not authorize any scorer. Offline extractor
candidates, rejection audits, and pool summaries remain diagnostic until this
gate is signed.

### 4.5 Dev Scorer Authorization

Required before running dev baseline/candidate scorer commands:

```text
provider_green_preflight_passed = true
source_collection_completed = true
source_manifests_signed = true
candidate_pool_promotion_signed = true
m2_8pre_offline_passed = true
sota_or_acceptance_baseline_frozen_before_scorer = true
dev20_manifest_ready = true
dev_holdout_disjoint = true
planned_dev_baseline_command:
planned_dev_candidate_command:
raw_artifact_storage_location:
compact_artifact_output_location:
baseline_compact_artifact_dir_clean = true
candidate_compact_artifact_dir_clean = true
repairs_jsonl_excluded_from_baseline_compact_dir = true
repairs_jsonl_excluded_from_candidate_compact_dir = true
raw_diagnostics_excluded_from_baseline_and_candidate_compact_dirs = true
dev_scorer_approval_owner:
huawei_acceptance_owner:
engineering_execution_owner:
approval_timestamp_utc:
```

Dev scorer authorization permits only signed dev scorer commands. It does not
authorize holdout scorer, full BFCL scorer, paired full-suite comparison, or any
external performance claim.

### 4.6 Holdout Scorer Authorization

Required before running holdout baseline/candidate scorer commands:

```text
dev_scorer_completed = true
dev_artifact_schema_passed = true
dev_stop_loss_passed = true
provider_green_preflight_passed = true
holdout20_manifest_ready = true
dev_holdout_disjoint = true
planned_holdout_baseline_command:
planned_holdout_candidate_command:
raw_artifact_storage_location:
compact_artifact_output_location:
baseline_compact_artifact_dir_clean = true
candidate_compact_artifact_dir_clean = true
repairs_jsonl_excluded_from_baseline_compact_dir = true
repairs_jsonl_excluded_from_candidate_compact_dir = true
raw_diagnostics_excluded_from_baseline_and_candidate_compact_dirs = true
holdout_scorer_approval_owner:
huawei_acceptance_owner:
engineering_execution_owner:
approval_timestamp_utc:
```

Holdout scorer authorization permits only signed holdout scorer commands. It
does not authorize full BFCL scorer or a full-suite claim. Holdout evidence may
only support an interim or narrow claim if Huawei signs that scope explicitly.

### 4.7 Full BFCL or Huawei Acceptance Scorer Authorization

Required before running full BFCL or Huawei acceptance scorer commands:

```text
holdout_scorer_completed = true
holdout_artifact_schema_passed = true
holdout_stop_loss_passed = true
provider_green_preflight_passed = true
sota_or_acceptance_baseline_frozen_before_scorer = true
benchmark_scope = full_suite | huawei_signed_scope
test_category = "" unless Huawei signs a narrower scope
GRC_BFCL_USE_RUN_IDS = 0 unless Huawei signs a narrower scope
GRC_BFCL_PARTIAL_EVAL = 0 unless Huawei signs a narrower scope
planned_full_baseline_command:
planned_full_candidate_command:
planned_paired_comparison_command:
raw_artifact_storage_location:
compact_artifact_output_location:
baseline_compact_artifact_dir_clean = true
candidate_compact_artifact_dir_clean = true
repairs_jsonl_excluded_from_baseline_compact_dir = true
repairs_jsonl_excluded_from_candidate_compact_dir = true
raw_diagnostics_excluded_from_baseline_and_candidate_compact_dirs = true
full_or_huawei_scorer_approval_owner:
huawei_acceptance_owner:
engineering_execution_owner:
approval_timestamp_utc:
```

Only this gate may produce formal BFCL performance evidence. A SOTA or `+3pp`
claim is still prohibited until paired scorer artifacts, run schemas, manifest
alignment, regression report, cost/latency report, acceptance decision, and
`absolute_delta_pp >= 3.0` all pass.

For every scorer gate, both baseline and candidate compact artifact directories
must exclude `repairs.jsonl`, `*_repair_records.jsonl`, logs, raw traces, raw
BFCL result/score trees, and other raw diagnostics. Raw diagnostics must stay in
the signed raw artifact storage location outside deliverable compact artifacts.

## 5. Dev, Holdout, and Full-Suite Relationship

Default Huawei performance acceptance scope is full BFCL unless Huawei explicitly
approves another scope in writing.

Allowed use:

| Scope | Allowed role | Claim allowed |
| --- | --- | --- |
| `dev20` | Internal scorer authorization, debugging, stop-loss | No external performance claim |
| `holdout20` | Overfit check before full-suite; candidate promotion gate | Interim claim only with explicit Huawei approval |
| `category` | Category-specific evidence | Category claim only with explicit Huawei approval |
| `full_suite` | Default formal Stage-1 BFCL performance evidence | Formal performance claim if all gates pass |

If Huawei requires full BFCL:

- `dev20`, `holdout20`, and category runs are prerequisite evidence only.
- They cannot be reported as full-suite improvement.
- Final acceptance requires full-suite baseline/candidate scorer artifacts under
  the frozen provider/model/protocol and `absolute_delta_pp >= 3.0`.

Full-suite hard pins:

```text
test_category = ""
GRC_BFCL_USE_RUN_IDS = 0
GRC_BFCL_PARTIAL_EVAL = 0
baseline evaluation_status = complete
candidate evaluation_status = complete
baseline/candidate manifest alignment = pass
unacceptable_regression_present = false
```

## 6. Final Sign-Off Checklist

All items must be checked before any formal Huawei Stage-1 BFCL performance claim.

```text
[ ] Provider HTTP 401/403 blockers are resolved.
[ ] provider_green_preflight_passed=true.
[ ] artifact_boundary_passed=true.
[ ] stage1_sota_comparison has no TBD blocking fields.
[ ] SOTA or accepted baseline is frozen before scorer execution.
[ ] calculation_unit=absolute_pp and required_delta_pp=3.0.
[ ] scope_change_route is approved and not `none`.
[ ] scope_change_approval_id is recorded.
[ ] scope_change_approved_before_execution=true.
[ ] deterministic_family_search_exhausted=true is acknowledged.
[ ] candidate pool readiness may be true only after the newly approved route passes its own gate.
[ ] explicit_ambiguous_literal_present=false.
[ ] no_leakage_check_passed=true.
[ ] dev20_manifest_ready=true.
[ ] holdout20_manifest_ready=true.
[ ] dev_holdout_disjoint=true.
[ ] manifest_case_integrity_passed=true.
[ ] m2_8pre_offline_passed=true.
[ ] scorer_authorization_ready=true.
[ ] scorer execution approval_id is recorded.
[ ] baseline compact artifact dir excludes repairs.jsonl and raw diagnostics.
[ ] candidate compact artifact dir excludes repairs.jsonl and raw diagnostics.
[ ] baseline run artifact schema passed.
[ ] candidate run artifact schema passed.
[ ] baseline/candidate manifest alignment passed.
[ ] paired_comparison.json is present.
[ ] regression_report.json is present.
[ ] cost_latency_report.json is present.
[ ] acceptance_decision.json is present.
[ ] absolute_delta_pp >= 3.0.
[ ] required_3pp_target_passed=true.
[ ] performance_claim_allowed=true.
[ ] scripts/check_stage1_bfcl_performance_ready.py --strict passes.
[ ] scripts/check_first_stage_bfcl_ready.py --strict passes.
```

## 7. Prohibited Claims Until Sign-Off

Do not claim any of the following while a hard gate is false:

- Huawei Stage-1 BFCL performance acceptance is complete.
- SOTA or `+3pp` has been achieved.
- Full-suite BFCL improvement exists.
- Dev20, holdout20, or category evidence is full-suite evidence.
- Memory-heavy explicit-obligation smoke is BFCL performance evidence.
- Postcondition-guided smoke is BFCL performance evidence.
- CTSPC-v0 is the first-stage performance route.
- Any rule is retained based only on dev evidence.

Allowed current claim while fail-closed:

```text
The repository is ready as a scaffold and diagnostic evidence package, but formal
Huawei Stage-1 BFCL performance acceptance remains blocked because deterministic
Stage-1 family search is exhausted and no candidate pool, scorer authorization,
paired BFCL scorer evidence, or +3pp absolute
improvement all pass.
```
