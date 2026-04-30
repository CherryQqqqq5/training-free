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
allowed_benchmark: BFCL
allowed_stage: stage1_formal_performance_acceptance
allowed_scopes: provider_preflight, source_collection
```

Required rules:

- `expected_api_key_env` must name the environment variable only. Do not paste
  the credential value into this repository, logs, markdown, JSON, shell history,
  or delivery artifacts.
- `credential_source` must name the approved secret manager, vault, or local
  operator handoff process, not the secret value.
- `base_url` must be sanitized in artifacts.
- `upstream_model_route`, `bfcl_model_alias`, and `runtime_config_path` must be
  identical for baseline and candidate unless Huawei explicitly approves a
  change.
- `allowed_categories` must list the exact BFCL categories permitted for
  provider preflight and source collection.
- `allowed_splits` must list the exact non-scorer splits permitted before
  scorer authorization. Provider unblock may authorize `provider_preflight` and
  `source_collection`; it must not authorize `dev20`, `holdout20`, category
  scorer, baseline scorer, candidate scorer, or full-suite scorer.
- `allowed_full_suite` must be explicit. If `yes`, it only means the credential
  can later be used for a separately signed full-suite scorer request after all
  gates pass.
- Budget and timeout fields must be filled before engineering runs provider
  preflight. Empty budget or timeout fields are a provider-unblock hard fail.

## 2. BFCL Preflight Checks

Engineering may run only provider preflight after the credential is installed.
The preflight must prove:

```text
credential_present = true
credential_value_logged = false
provider_profile = approved value
expected_api_key_env = approved env var name
base_url = approved sanitized base URL
upstream_model_route = approved route
bfcl_model_alias = approved alias
runtime_config_path = approved path
allowed_categories = approved list
allowed_splits = provider_preflight, source_collection
budget_timeout_policy_present = true
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
- Missing or ambiguous allowed categories, allowed splits, budget, timeout, rate
  limit, retry policy, or sign-off owner.
- Tool-call, text-response, trace-emission, or BFCL-compatible response check
  fails.
- Raw credential, raw provider response, raw trace tree, or `.env` is captured in
  committed artifacts.
- Source collection compact artifact directories contain `repairs.jsonl`,
  `*_repair_records.jsonl`, logs, raw traces, raw BFCL result/score trees, or
  other raw diagnostics. Raw diagnostics must stay outside deliverable
  `outputs/artifacts/...` compact artifact directories.

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
allowed_categories
allowed_splits
max_requests
request_timeout_seconds
overall_timeout_minutes
rate_limit_policy
retry_policy
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
budget_owner:
provider_profile:
expected_api_key_env:
base_url:
upstream_model_route:
bfcl_model_alias:
runtime_config_path:
allowed_categories:
allowed_splits:
allowed_full_suite:
max_requests:
max_input_tokens:
max_output_tokens:
request_timeout_seconds:
overall_timeout_minutes:
retry_policy:
rate_limit_policy:
approval_timestamp_utc:
```

Provider access approval allows engineering to run provider preflight only. It
does not automatically authorize source collection, baseline scorer, candidate
scorer, or full-suite scorer.

Post-provider approval sequence:

```text
1. Provider unblock sign-off after provider_green_preflight_passed=true.
2. Source collection sign-off after approved provider/model route is frozen and
   compact source artifacts pass boundary checks.
3. Scorer authorization sign-off after source collection evidence, no-leakage
   checks, dev/holdout disjointness, SOTA/baseline freeze, and
   explicit_literal_candidate_pool_passed=true are all recorded.
```

Scorer authorization requires a separate completed request in
`docs/stage1_huawei_acceptance_approval_template.md` after provider green passes,
SOTA/baseline freeze is complete, no-leakage checks pass, and dev/holdout
manifests are disjoint. For the explicit-only route, it also requires
`explicit_literal_candidate_pool_passed=true`.

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
