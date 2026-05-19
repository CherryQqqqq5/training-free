# Stage1 ABHE-v0 provider transport backoff policy — design

Status: `declarative-only spec` on feature branch
`feat/provider-transport-backoff-policy`. This document does NOT claim
performance, +3pp, Huawei acceptance, or any scorer/holdout/full-suite
evidence. `policy_enabled = false` and `policy_wired_into_proxy = false`.

## What P3 is

A **separate YAML file**
(`configs/runtime_bfcl_provider_transport_backoff_policy.yaml`) carrying
a declarative backoff/retry policy spec, plus an offline validator that
cross-checks it against `configs/runtime_bfcl_structured.yaml`.

The validator:
- reads both YAMLs (no provider, no proxy)
- asserts the policy block is well-shaped (whitelist + bounds)
- asserts `policy_enabled == False` (master switch)
- asserts `per_request_timeout_sec < runtime.timeout_sec`
- asserts `retry_on_status_codes` is subset of transient-class set
  `{408, 425, 429, 500, 502, 503, 504, 522, 524}`
- asserts `jitter_strategy ∈ {none, equal_jitter, full_jitter, decorrelated_jitter}`
- asserts all 10 `*_authorized_by_this_policy` booleans are False
- emits a compact artifact under
  `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_provider_transport_backoff_policy.json`

## What P3 is NOT

- NOT a proxy modification
- NOT a provider call
- NOT a scorer call
- NOT a BFCL generate/evaluate call
- NOT an authorization (the policy itself attests it does not authorize)
- NOT a modification of `configs/runtime_bfcl_structured.yaml` (test
  `test_runtime_yaml_unchanged_by_this_branch` enforces this)
- NOT a rerun
- NOT performance / +3pp / Huawei evidence

## Why this design

C3 (operational root cause from CLAUDE_RESUME): provider 504s on
multi_turn_miss_param distinct rerun. P3 lays the **declarative
groundwork** for proxy-side retry without committing to a wiring step
or a rerun. P1.5b sign + a separate wire-step PR can flip
`policy_enabled` to True; until then the spec is harmless.

Literature anchors (cited in builder header):

- **Brooker (AWS, 2015), "Exponential Backoff and Jitter"** — Full
  Jitter (sleep ~ Uniform(0, min(cap, base*2^n))) chosen for low
  coordination overhead and resilient throughput under contention.
- **"Beyond Max Tokens" (arxiv 2025)** — multi-turn tool chains can
  amplify cost 100-658x. Hard caps (`max_total_retry_time_sec=60`,
  `abort_run_after_consecutive_504s=5`) defend against the same class.
- **BFCL-v3 multi-turn blog (Berkeley 2024)** — timeouts and 504s are
  the dominant transient failure mode on extended categories like
  multi_turn_miss_param.

## Policy values (rationale)

Field | Value | Rationale
---|---|---
`max_retries` | 3 | enough for transient 5xx; bounded against cost amp
`initial_delay_ms` | 500 | balances responsiveness vs upstream pressure
`max_delay_ms` | 8000 | bounded so single retry can't dominate budget
`multiplier` | 2.0 | classical exponential
`jitter_strategy` | `full_jitter` | AWS-recommended default
`per_request_timeout_sec` | 45 | < runtime.timeout_sec (120); leaves room for 2-3 retries inside run budget
`retry_on_status_codes` | `[502, 503, 504]` | conservative; transient upstream class only
`hard_caps.max_total_retry_time_sec` | 60 | half of runtime budget
`hard_caps.max_concurrent_in_flight_requests` | 4 | reduces upstream pressure on miss_param batch
`hard_caps.abort_run_after_consecutive_504s` | 5 | aborts a wedged run early

## Boundary invariants (must remain True)

- `policy_enabled = False`
- `policy_wired_into_proxy = False`
- All raw-material attestations False
- All performance / acceptance attestations False
- All `*_authorized_by_this_policy` booleans False
- `provider_calls_made = False`, `bfcl_generate_called = False`,
  `bfcl_evaluate_called = False`, `scorer_called = False`

## Files added on this branch

- `configs/runtime_bfcl_provider_transport_backoff_policy.yaml`
- `scripts/build_abhe_v0_provider_transport_backoff_policy.py`
- `scripts/check_abhe_provider_transport_backoff_policy_ready.py`
- `tests/test_abhe_v0_provider_transport_backoff_policy.py`
- `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_provider_transport_backoff_policy.json`
- `docs/stage1_provider_transport_backoff_policy_design.md`

No modification of any existing file.

## Pre-merge gate (must all hold)

- 6 core ABHE checkers (unchanged from main)
- v3 skeleton checker (P2): exit 0
- new P3 checker: exit 0
- 11 ABHE test files (10 existing + 1 new P3): all pass
- working tree clean post-test
