# Stage-1 Huawei Acceptance Approval Template

This document is the approval template for the formal Stage-1 BFCL performance
acceptance path. It is not a scaffold handoff note and it does not authorize
scorer execution by itself.

Current repository state is fail-closed:

- Formal BFCL performance acceptance: `not ready`
- Provider green preflight: `not passed`
- Current provider blocker: HTTP `401` class failures for attempted provider
  profiles
- M2.8-pre scorer authorization: `not ready`
- Paired BFCL score chain: `not present`
- Allowed claim today: scaffold and diagnostic evidence package only

Related provider unblock documents:

```text
docs/stage1_provider_access_request.md
outputs/artifacts/stage1_bfcl_acceptance/provider_unblock_request.md
```

## 1. Provider Green Artifact

The approval package must archive compact provider evidence before any source
collection or scorer run.

Required artifacts:

```text
outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json
outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.md
<baseline_or_candidate_run>/artifacts/preflight_report.json
scripts/check_provider_green_preflight.py --compact --strict
scripts/check_artifact_boundary.py
```

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
candidate_family: explicit_required_arg_literal_completion
candidate_generatable_count:
retain_eligible_candidate_count:
combined_retain_eligible_candidate_count:
explicit_ambiguous_literal_present:
no_leakage_check_passed:
dev20_manifest_ready:
holdout20_manifest_ready:
dev_holdout_disjoint:
manifest_case_integrity_passed:
m2_8pre_offline_passed:
scorer_authorization_ready:
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
- `m2_8pre_offline_passed=true`
- `scorer_authorization_ready=true`
- `candidate_family=explicit_required_arg_literal_completion`
- `candidate_generatable_count >= 35`
- `retain_eligible_candidate_count >= 35`
- `combined_retain_eligible_candidate_count >= 35`
- `explicit_ambiguous_literal_present=false`
- `no_leakage_check_passed=true`
- `dev_holdout_disjoint=true`
- `manifest_case_integrity_passed=true`
- SOTA or accepted baseline comparator is frozen before scorer execution

No-leakage requirements:

- Candidate rules may use only schema-local, current-request, or current
  observation evidence.
- Candidate rules must not use scorer gold, hidden source results, case ids,
  target labels, raw scorer feedback, or post-hoc scorer outcomes as trigger or
  argument sources.
- Candidate rules must not change provider, model, evaluator, BFCL tool schema,
  trajectory order, or tool choice unless separately approved.

## 4. Dev, Holdout, and Full-Suite Relationship

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

## 5. Final Sign-Off Checklist

All items must be checked before any formal Huawei Stage-1 BFCL performance claim.

```text
[ ] Provider HTTP 401/403 blockers are resolved.
[ ] provider_green_preflight_passed=true.
[ ] artifact_boundary_passed=true.
[ ] stage1_sota_comparison has no TBD blocking fields.
[ ] SOTA or accepted baseline is frozen before scorer execution.
[ ] calculation_unit=absolute_pp and required_delta_pp=3.0.
[ ] candidate_family=explicit_required_arg_literal_completion.
[ ] candidate_generatable_count >= 35.
[ ] retain_eligible_candidate_count >= 35.
[ ] combined_retain_eligible_candidate_count >= 35.
[ ] explicit_ambiguous_literal_present=false.
[ ] no_leakage_check_passed=true.
[ ] dev20_manifest_ready=true.
[ ] holdout20_manifest_ready=true.
[ ] dev_holdout_disjoint=true.
[ ] manifest_case_integrity_passed=true.
[ ] m2_8pre_offline_passed=true.
[ ] scorer_authorization_ready=true.
[ ] scorer execution approval_id is recorded.
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

## 6. Prohibited Claims Until Sign-Off

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
Huawei Stage-1 BFCL performance acceptance remains blocked until provider green
preflight, scorer authorization, paired BFCL scorer evidence, and +3pp absolute
improvement all pass.
```
