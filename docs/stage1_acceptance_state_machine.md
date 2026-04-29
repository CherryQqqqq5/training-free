# Stage-1 Acceptance State Machine

This document defines the fail-closed state machine for formal Stage-1 BFCL
performance acceptance. It is an approval contract, not evidence that any state
has already passed.

Current state: `provider_blocked`.

## State Order

```text
provider_blocked
-> provider_green
-> source_collection_ready
-> candidate_pool_ready
-> scorer_authorized
-> dev_scored
-> holdout_scored
-> full_bfcl_scored
-> +3pp_claim_ready
```

No state may be skipped. A later state is invalid if any earlier state later
fails or if provider/model/protocol drift is detected.

## 1. provider_blocked

Enter criteria:

- Provider access is missing or failing.
- Current blocker includes HTTP `401` or `403`.
- `provider_green_preflight_passed=false`.

Exit criteria:

- Valid provider credential is approved without exposing the credential value.
- Frozen provider profile, API key env var name, base URL, model route, BFCL
  model alias, and runtime config path are recorded.
- Provider green preflight is approved as the transition gate to
  `provider_green`.

Allowed activity:

```text
Review and maintain offline scaffold artifacts only:
outputs/artifacts/stage1_bfcl_acceptance/source_collection_dry_command_pack.md
outputs/artifacts/stage1_bfcl_acceptance/source_collection_dry_command_pack.json
docs/explicit_literal_candidate_expansion_spec.md
scripts/build_explicit_literal_candidate_pool.py
tests/test_build_explicit_literal_candidate_pool.py
```

The dry command pack is an offline planning artifact. It must not call the
provider, BFCL, a model, or a scorer. Provider preflight is only the approved
transition gate after a valid credential is installed; source collection and
scorer commands remain prohibited while the current state is `provider_blocked`.

Extractor skeleton and fixture-matrix implementation are allowed in
`provider_blocked` only when they remain offline-only and fail-closed:

- They may define parser contracts, fixture matrices, schemas, unit tests, and
  scaffold output locations.
- They may read synthetic fixtures or already-committed compact scaffold inputs.
- They must report `extractor_skeleton_only=true` or otherwise fail closed until
  real source collection artifacts exist and the extractor implementation is
  explicitly enabled.
- Their outputs may be committed only as scaffold evidence, not as source
  collection evidence, candidate pool readiness, scorer authorization, BFCL
  performance evidence, or SOTA/`+3pp` evidence.
- They must keep `does_not_call_provider=true`,
  `does_not_call_bfcl_or_model=true`, and `does_not_authorize_scorer=true`.

Generated empty/default extractor artifacts are allowed in `provider_blocked`
only as scaffold or fixture evidence. This includes empty `candidate_rules.jsonl`
files, default dev/holdout manifests, fixture matrices, and skeleton build
summaries. To avoid being mistaken for source collection or scorer evidence,
each generated JSON/markdown summary or manifest must label the boundary with
the equivalent of:

```text
acceptance_state = provider_blocked
offline_only = true
scaffold_evidence_only = true
fixture_or_skeleton_output = true
source_collection_evidence = false
candidate_pool_ready = false
scorer_authorization_ready = false
performance_claim_ready = false
does_not_call_provider = true
does_not_call_bfcl_or_model = true
does_not_authorize_scorer = true
```

Empty/default artifacts must not use names, headings, or `ready=true` fields
that imply source collection completion, candidate pool readiness, dev/holdout
approval, scorer authorization, or BFCL performance evidence. If a generated
artifact contains real candidate rows or selected dev/holdout cases, it is no
longer treated as an empty/default scaffold artifact and must pass the later
`candidate_pool_ready` gates before any acceptance claim can cite it.

R1 rejected records, rejection taxonomy rows, extractor audit rows, and
extractor summaries are scaffold diagnostic evidence only while the state is
`provider_blocked`; they must not count toward the 35+ candidate pool, source
collection evidence, scorer authorization, or any SOTA/`+3pp` claim.

Prohibited claim:

- Provider green.
- Source collection ready.
- Candidate pool ready.
- Scorer authorized.
- Stage-1 BFCL acceptance complete.
- SOTA or `+3pp` achieved.

Prohibited commands:

- Source collection reruns.
- Live provider calls.
- BFCL/model runs.
- Baseline scorer.
- Candidate scorer.
- Paired comparison.
- Full-suite BFCL evaluation.

## 2. provider_green

Enter criteria:

- `provider_green_preflight_passed=true`.
- `artifact_boundary_passed=true`.
- No unresolved HTTP `401` or `403`.
- Provider credential value is not logged or committed.
- Provider/model/protocol route is frozen for Stage-1.

Exit criteria:

- Provider unblock is signed.
- Source collection scope is approved.
- Source collection command plan and output artifact boundary are recorded.

Allowed commands:

```bash
python scripts/check_provider_green_preflight.py --compact --strict
python scripts/check_artifact_boundary.py
```

After provider unblock sign-off, engineering may run the approved source
collection commands recorded in the source collection request.

This state authorizes only the provider unblock and source collection path. It
does not authorize baseline scorer, candidate scorer, paired comparison, dev
scorer, holdout scorer, or full-suite scorer execution.

Prohibited claim:

- Scorer authorized.
- Dev, holdout, or full-suite scored.
- Full-suite BFCL improvement.
- SOTA or `+3pp` achieved.

## 3. source_collection_ready

Enter criteria:

- Provider unblock is signed.
- Source collection scope, model route, provider profile, BFCL protocol, and
  runtime config are frozen.
- Compact source collection artifact path and raw artifact storage boundary are
  recorded.
- Source collection does not expose raw provider responses, traces, `.env`, or
  credential values in committed artifacts.

Exit criteria:

- Source collection artifacts exist and pass artifact boundary checks.
- Candidate generation inputs are frozen.
- No-leakage rule source boundary is recorded.

Allowed commands:

```bash
python scripts/check_artifact_boundary.py
```

Engineering may run only the approved source collection commands for the frozen
provider/model/protocol.

Prohibited claim:

- Candidate pool ready.
- Scorer authorized.
- Any scorer result.
- SOTA or `+3pp` achieved.

## 4. candidate_pool_ready

Enter criteria:

- Source collection artifacts are complete enough to build the candidate pool.
- `candidate_family=explicit_required_arg_literal_completion`.
- Candidate rules use only schema-local, current-request, or current-observation
  evidence.
- Dev/holdout manifests are prepared for disjointness checks.

Exit criteria:

- `explicit_literal_candidate_pool_passed=true`.
- `candidate_generatable_count >= 35`.
- `retain_eligible_candidate_count >= 35`.
- `combined_retain_eligible_candidate_count >= 35`.
- `explicit_ambiguous_literal_present=false`.
- No-leakage checks pass.
- Dev/holdout disjointness and manifest case integrity pass.
- SOTA or accepted same-protocol baseline is frozen before scorer execution.

Allowed commands:

```bash
python scripts/check_explicit_literal_candidate_pool.py --compact --strict
python scripts/check_m28pre_offline.py --compact --strict
python scripts/check_artifact_boundary.py
```

Prohibited claim:

- Scorer authorized.
- Dev, holdout, or full-suite scored.
- SOTA or `+3pp` achieved.
- Candidate pool evidence is BFCL performance evidence.

## 5. scorer_authorized

Enter criteria:

- `provider_green_preflight_passed=true`.
- `artifact_boundary_passed=true`.
- `m2_8pre_offline_passed=true`.
- `explicit_literal_candidate_pool_passed=true`.
- No-leakage checks pass.
- Dev/holdout are disjoint.
- SOTA or accepted baseline is frozen before scorer execution.
- Scorer authorization request is signed with planned baseline and candidate
  commands.

Exit criteria:

- Dev scorer commands complete and compact dev artifacts pass schema checks.

Allowed commands:

```bash
python scripts/check_bfcl_run_artifact_schema.py --strict <dev_run_root>
python scripts/check_artifact_boundary.py
```

Engineering may run only the signed dev baseline/candidate scorer commands.

Prohibited claim:

- Holdout scored.
- Full-suite scored.
- Full-suite BFCL improvement.
- SOTA or `+3pp` achieved.

## 6. dev_scored

Enter criteria:

- Signed dev baseline/candidate scorer run completed.
- Dev run artifact schemas pass.
- Provider/model/protocol match the frozen comparator.
- Dev paired comparison is present for internal triage only.

Exit criteria:

- Dev results do not trigger stop-loss criteria.
- Holdout scorer request is approved.
- Provider green remains valid.

Allowed commands:

```bash
python scripts/check_bfcl_run_artifact_schema.py --strict <dev_run_root>
python scripts/check_bfcl_paired_comparison.py --strict --acceptance-root outputs/artifacts/stage1_bfcl_acceptance --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json
python scripts/check_artifact_boundary.py
```

Prohibited claim:

- Holdout or full-suite improvement.
- Dev20 evidence as full-suite evidence.
- SOTA or `+3pp` achieved.

## 7. holdout_scored

Enter criteria:

- Signed holdout baseline/candidate scorer run completed.
- Holdout run artifact schemas pass.
- Holdout set is disjoint from dev.
- Provider/model/protocol match the frozen comparator.

Exit criteria:

- Holdout results do not trigger stop-loss criteria.
- Full BFCL scorer request is approved, or Huawei explicitly approves a narrower
  category claim in writing.
- Provider green remains valid.

Allowed commands:

```bash
python scripts/check_bfcl_run_artifact_schema.py --strict <holdout_run_root>
python scripts/check_bfcl_paired_comparison.py --strict --acceptance-root outputs/artifacts/stage1_bfcl_acceptance --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json
python scripts/check_artifact_boundary.py
```

Prohibited claim:

- Holdout20 evidence as full-suite evidence.
- Full-suite BFCL improvement unless full-suite is scored and passes.
- SOTA or `+3pp` achieved unless Huawei has explicitly approved holdout-only
  acceptance scope.

## 8. full_bfcl_scored

Enter criteria:

- Full-suite baseline/candidate scorer run is signed and completed.
- `test_category=""`.
- `GRC_BFCL_USE_RUN_IDS=0`.
- `GRC_BFCL_PARTIAL_EVAL=0`.
- Baseline and candidate evaluation status are complete.
- Baseline/candidate manifest alignment passes.
- Run artifact schemas pass.
- Paired comparison, regression report, cost/latency report, and acceptance
  decision artifacts exist.

Exit criteria:

- Absolute paired delta is computed in percentage points.
- Regression and cost/latency gates pass.
- Acceptance decision records whether `absolute_delta_pp >= 3.0`.

Allowed commands:

```bash
python scripts/check_bfcl_run_artifact_schema.py --strict <full_suite_run_root>
python scripts/check_bfcl_paired_comparison.py --strict --acceptance-root outputs/artifacts/stage1_bfcl_acceptance --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json
python scripts/check_stage1_bfcl_performance_ready.py --compact --strict
python scripts/check_artifact_boundary.py
```

Prohibited claim:

- SOTA or `+3pp` achieved if `absolute_delta_pp < 3.0`.
- Stage-1 BFCL acceptance complete if any hard gate remains false.

## 9. +3pp_claim_ready

Enter criteria:

- `full_bfcl_scored` is complete, or Huawei has explicitly signed a narrower
  scope for the claim.
- `calculation_unit=absolute_pp`.
- `required_delta_pp=3.0`.
- `absolute_delta_pp >= 3.0`.
- `required_3pp_target_passed=true`.
- `performance_claim_allowed=true`.
- `scripts/check_stage1_bfcl_performance_ready.py --strict` passes.
- `scripts/check_first_stage_bfcl_ready.py --strict` passes.

Exit criteria:

- Huawei acceptance owner signs the final Stage-1 BFCL performance acceptance.
- Claim text names the exact scope: full-suite, category, dev20, or holdout20.
- Claim text does not imply full-suite if the approved scope is narrower.

Allowed commands:

```bash
python scripts/check_stage1_bfcl_performance_ready.py --compact --strict
python scripts/check_first_stage_bfcl_ready.py --compact --strict
python scripts/check_artifact_boundary.py
```

Prohibited claim:

- Any broader scope than the signed scorer scope.
- Any relative-percent `+3%` claim unless separately approved and clearly
  labeled as non-default.
- Any claim that hides provider/model/protocol, BFCL version, scope, or
  comparator.

## Global Fail-Closed Rules

- Any provider HTTP `401` or `403` returns the state to `provider_blocked`.
- Any provider/model/protocol drift returns the state to the last signed state
  before the drift.
- Any credential value, `.env`, raw provider response, raw trace tree, raw BFCL
  result tree, or hidden scorer feedback in committed artifacts blocks all
  outward acceptance claims.
- Dev20, holdout20, and category evidence are not full-suite evidence unless
  Huawei explicitly signs that narrower scope.
- SOTA or accepted baseline must be frozen before scorer execution.
- The default `+3` calculation is absolute percentage points.
