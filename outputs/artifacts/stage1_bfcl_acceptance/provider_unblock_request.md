# Provider Unblock Request

Current Stage-1 BFCL performance acceptance status is fail-closed.

## Current Blocker

```text
blocker_id: provider_http_401
severity: P0
provider_green_preflight_passed: false
scorer_authorization_ready: false
formal_bfcl_performance_acceptance_ready: false
```

Observed state: attempted provider access is failing with HTTP `401` class
authentication errors. This blocks source collection, baseline scorer, candidate
scorer, paired comparison, and full-suite BFCL performance claims.

## Required Next Action

Provide and approve a valid provider credential for the requested Stage-1 BFCL
provider profile. The credential must be supplied through the approved
environment variable only; do not commit or paste the credential value into this
repository.

Approval details must be recorded in:

```text
docs/stage1_provider_access_request.md
docs/stage1_huawei_acceptance_approval_template.md
```

## After Credential Is Available

Engineering may run provider green preflight only:

```bash
python scripts/check_provider_green_preflight.py --compact --strict
python scripts/check_artifact_boundary.py
```

Expected success evidence:

```text
outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json
outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.md
provider_green_preflight_passed = true
artifact_boundary_passed = true
```

## Still Prohibited

Until provider green preflight passes and scorer authorization is separately
approved, do not run:

```text
source collection rerun
baseline scorer
candidate scorer
paired BFCL comparison
full-suite BFCL evaluation
category or holdout scorer used for external claim
```

After provider green preflight passes, the acceptance sequence is:

```text
1. Sign provider unblock.
2. Sign source collection scope and compact artifact boundary.
3. Sign scorer authorization only after no-leakage, dev/holdout disjointness,
   SOTA/baseline freeze, and explicit_literal_candidate_pool_passed=true.
```

Do not claim:

```text
Stage-1 BFCL acceptance complete
SOTA / +3pp achieved
full-suite BFCL improvement
provider green
scorer authorized
```

## Sign-Off Fields

```text
provider_access_approval_owner:
credential_owner:
huawei_acceptance_owner:
engineering_execution_owner:
provider_approval_id:
expected_api_key_env:
provider_profile:
upstream_model_route:
bfcl_model_alias:
runtime_config_path:
approval_timestamp_utc:
```
