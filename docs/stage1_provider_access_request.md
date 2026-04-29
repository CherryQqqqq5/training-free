# Stage-1 Provider Access Request

This document turns the current provider HTTP `401` blocker into an executable
access request for Stage-1 BFCL performance acceptance. It does not authorize
provider execution by itself; it defines what must be approved before engineering
can run provider preflight and later request scorer authorization.

Current state: provider access is blocked by HTTP `401` class failures. Do not
run source collection, baseline scorer, candidate scorer, or full-suite scorer
until a valid credential is approved and provider green preflight passes.

## 1. Requested Provider Profile

The approver must provide or confirm all fields below.

```text
provider_profile:
provider_approval_id:
approval_owner:
approval_timestamp_utc:
expected_api_key_env:
credential_source:
credential_rotation_owner:
base_url:
upstream_model_route:
bfcl_model_alias:
runtime_config_path:
allowed_benchmark: BFCL
allowed_stage: stage1_formal_performance_acceptance
allowed_scopes: preflight, source_collection, baseline_scorer, candidate_scorer
```

Required rules:

- `expected_api_key_env` must name the environment variable only. Do not paste
  the credential value into this repository, logs, markdown, JSON, shell history,
  or delivery artifacts.
- `base_url` must be sanitized in artifacts.
- `upstream_model_route`, `bfcl_model_alias`, and `runtime_config_path` must be
  identical for baseline and candidate unless Huawei explicitly approves a
  change.
- The approval must specify whether the credential is allowed for full-suite
  BFCL, category BFCL, `dev20`, and `holdout20`.

## 2. BFCL Preflight Checks

Engineering may run only provider preflight after the credential is installed.
The preflight must prove:

```text
credential_present = true
credential_value_logged = false
upstream_auth_passed = true
model_route_available = true
bfcl_compatible_response = true
chat_tool_call = pass
responses_tool_call = pass
chat_text_response = pass
trace_emission = pass
source_collection_rerun_ready = true
candidate_evaluation_ready = true
provider_green_preflight_passed = true
```

Hard fail:

- HTTP `401` or `403`.
- Missing credential environment variable.
- Wrong provider profile, base URL, model route, BFCL model alias, or runtime
  config path.
- Tool-call, text-response, trace-emission, or BFCL-compatible response check
  fails.
- Raw credential, raw provider response, raw trace tree, or `.env` is captured in
  committed artifacts.

## 3. Success Artifacts

The approved preflight must produce compact evidence only:

```text
outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json
outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.md
<run_dir>/artifacts/preflight_report.json
```

Required validation commands after the preflight artifact exists:

```bash
python scripts/check_provider_green_preflight.py --compact --strict
python scripts/check_artifact_boundary.py
```

The success artifact must include:

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
provider_green_preflight_passed = true
artifact_boundary_passed = true
```

## 4. Failure Artifacts

If provider preflight fails, archive only compact failure evidence:

```text
outputs/artifacts/stage1_bfcl_acceptance/provider_unblock_request.md
outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json
outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.md
```

Failure artifacts must state:

```text
provider_green_preflight_passed = false
failure_class = auth_401 | auth_403 | route_unavailable | bfcl_incompatible | artifact_boundary_failure | other
scorer_authorization_ready = false
formal_bfcl_performance_acceptance_ready = false
next_required_action
```

Failure artifacts must not include credential values, raw provider payloads, raw
BFCL outputs, raw trace trees, repair records, or hidden scorer feedback.

## 5. Approval Owner and Execution Boundary

Required approvals:

```text
provider_access_approval_owner:
credential_owner:
huawei_acceptance_owner:
engineering_execution_owner:
```

Provider access approval allows engineering to run provider preflight only. It
does not automatically authorize source collection, baseline scorer, candidate
scorer, or full-suite scorer.

Scorer authorization requires a separate completed request in
`docs/stage1_huawei_acceptance_approval_template.md` after provider green passes,
SOTA/baseline freeze is complete, no-leakage checks pass, and dev/holdout
manifests are disjoint.

## 6. Commands Allowed After Credential Approval

Allowed after credential installation:

```bash
python scripts/check_provider_green_preflight.py --compact --strict
python scripts/check_artifact_boundary.py
```

Allowed only after provider green and separate scorer authorization:

```bash
# Baseline BFCL scorer command recorded in scorer authorization request.
# Candidate BFCL scorer command recorded in scorer authorization request.
# Paired comparison command recorded in scorer authorization request.
python scripts/check_bfcl_run_artifact_schema.py --strict <run_root>
python scripts/check_bfcl_paired_comparison.py --strict --acceptance-root outputs/artifacts/stage1_bfcl_acceptance --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json
```

## 7. Commands Prohibited Until Provider Green and Scorer Authorization

Do not run:

```text
source collection rerun
baseline scorer
candidate scorer
paired BFCL comparison
full-suite BFCL evaluation
category BFCL evaluation for claim
holdout20 scorer for claim
any command that writes raw provider responses into committed artifacts
any command that logs or persists the credential value
```

Do not claim:

```text
provider green
scorer authorized
Stage-1 BFCL acceptance complete
SOTA / +3pp achieved
full-suite BFCL improvement
```

until the corresponding gates are complete and signed.
