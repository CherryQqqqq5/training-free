# First-Stage Acceptance Matrix

This document translates the first-stage Huawei acceptance target into repo-local
gates. It is an execution contract, not a performance claim.

## Acceptance Position

- Primary benchmark: BFCL-first.
- Secondary benchmarks: HLE or other suites are out of scope unless Huawei
  explicitly changes the acceptance target.
- Current delivery claim: scaffold and diagnostic evidence package only.
- Current performance claim: SOTA +3pp is not ready.
- Related repo documents: `docs/m28pre_delivery_summary.md`,
  `docs/bfcl_performance_roadmap.md`, `docs/theory_family_retention_ranking.md`,
  and `docs/memory_operation_dev_scorer_application.md`.


## Current Active Status

Provider technical preflight is green for Chuangzhi/Novacode `gpt-5.2`, but
provider green is not scorer authorization. Deterministic Stage-1 family search
is exhausted under current approved gates. Current branch status is
diagnostic/negative-evidence handoff only: no source expansion, scorer,
candidate pool, dev/holdout, full-suite, SOTA/+3pp, or Huawei acceptance claim
is authorized. See `docs/stage1_bfcl_negative_evidence_report.md`,
`docs/stage1_bfcl_scope_change_decision_memo.md`,
`outputs/artifacts/stage1_bfcl_acceptance/active_evidence_index.json`, and
`outputs/artifacts/stage1_bfcl_acceptance/performance_ready.json`.

## Fixed BFCL Protocol

Use `docs/experiment_protocol_bfcl_v4.md` as the protocol source of truth.

- Evaluator package: `bfcl-eval==2025.12.17`.
- Official reproduction anchor: `f7cf735`.
- Evaluator internals must not be modified.
- Baseline and candidate must use the same `protocol_id`, `test_category`,
  `bfcl_model_alias`, `upstream_profile`, and `upstream_model_route`.
- `evaluation_status` must be `complete` for both baseline and candidate before
  selector or acceptance comparison.
- Incomplete runs cannot be converted into synthetic zero-score candidates.

## Benchmark Scope

Default acceptance scope is BFCL full-suite. Dev/holdout subsets are allowed only
as pre-registered gates before full-suite execution.

| Stage | Purpose | Minimum condition | Claim allowed |
| --- | --- | --- | --- |
| Offline gate | Decide whether scorer can be planned | Clean artifact boundary, M2.8-pre scorer authorization, valid dev/holdout manifests | No performance claim |
| Dev20 | First controlled signal | Same protocol baseline/candidate, complete metrics, positive net gain, no regression blocker | Internal diagnostic claim only |
| Holdout20 | Overfit check | Same protocol baseline/candidate, complete metrics, positive net gain, disjoint from dev | Candidate can be proposed for full-suite |
| Full BFCL | Acceptance evidence | Same protocol baseline/candidate, complete metrics, at least +3 absolute accuracy points over accepted baseline | First-stage performance claim |

## SOTA and +3pp Definition

Until Huawei supplies an external leaderboard target, this repo uses same-model,
same-provider, same-protocol baseline as the enforceable local comparator.

- `+3pp` means absolute accuracy-point gain, not relative percent gain.
- Baseline and candidate must run on the same evaluator package, BFCL alias,
  upstream route, provider profile, context limits, tool list, and run category.
- If Huawei requires an external SOTA comparator, the comparator snapshot date,
  model scale, provider, and BFCL version must be recorded before execution.
- If the result is below +3pp or any required run is incomplete, the report must
  fail closed and state that the performance claim is not ready.

The roadmap gate is stricter before any full-suite or leaderboard claim: freeze
the protocol and clean baseline, scan opportunity offline, pass a paired subset,
then expand only after positive net gain and bounded cost/latency.

## Provider and Model Boundary

The repo currently documents OpenAI-compatible BFCL proxy execution with
`novacode` / 创智 as the only approved Stage-1 BFCL relay profile; OpenRouter is not used for this sprint.
Acceptance runs must freeze the provider before execution.

Required manifest fields:

- `bfcl_model_alias`
- `upstream_profile`
- `upstream_model_route`
- `protocol_id`
- `test_category`
- `git_sha`
- `git_dirty`

`git_dirty=true` does not automatically invalidate a run, but it is a
reproducibility warning and must be disclosed.

Provider note: memory-only dev scorer materials may require `novacode` or
Huawei/Chuangzhi provider routing. That does not make the memory line a BFCL
performance mainline, and it does not override the BFCL protocol matrix unless
Huawei explicitly freezes that provider for acceptance.

## Authorized First-Stage Performance Route

No candidate family is currently authorized for performance. Deterministic
argument/tool-use families were approved diagnostics and are now zero-yield under
current gates.

Previously diagnosed families:

- `explicit_required_arg_literal_completion`
- `wrong_arg_key_alias_repair`
- `deterministic_schema_local_non_live_repair`
- structural malformed/final-before-tool
- emitted tool-name/schema normalization
- schema retrieval/rerank feasibility

Disallowed as first-stage performance main claims:

- CTSPC-v0, because current durable scorer evidence is diagnostic and negative.
- Memory-operation smoke, because current evidence is offline/runtime-readiness
  only and needs separate approval before any scorer.
- Postcondition-guided smoke, because current stop-loss and source-scope gates do
  not support a performance claim.

## Required Local Gates

Run these before any handoff:

```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest -q
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
PYTHONPATH=.:src .venv/bin/python scripts/check_provider_green_preflight.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_m28pre_offline.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_paired_comparison.py --acceptance-root outputs/artifacts/stage1_bfcl_acceptance --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_stage1_bfcl_performance_ready.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_first_stage_bfcl_ready.py --compact --strict
```

`check_explicit_obligation_smoke_ready.py --compact` is a secondary diagnostic
gate for the memory-heavy explicit-obligation lane. It is expected to remain
fail-closed unless that lane is explicitly reselected and approved; it does not
block the current diagnostic/negative-evidence handoff.

Expected current behavior is fail-closed for first-stage performance acceptance.
`check_first_stage_bfcl_ready.py --strict` should exit non-zero until a clean
artifact boundary, scorer authorization, and reproducible BFCL gain exist.

## Acceptance Decision

Huawei acceptance is ready only when all are true:

- `artifact_boundary_passed=true`
- provider green preflight has passed against the frozen provider/model route
- `m2_8pre_offline_passed=true`
- `scorer_authorization_ready=true`
- `manifest_case_integrity_passed=true`
- baseline and candidate BFCL runs are complete and protocol-aligned
- paired comparison, regression report, cost/latency report, and acceptance
  decision artifacts exist
- full-suite or Huawei-approved holdout evidence shows at least +3pp gain
- `formal_bfcl_performance_ready=true`
- `sota_3pp_claim_ready=true`

If any item is false, the valid delivery is a scaffold/diagnostic handoff, not a
first-stage performance acceptance package.
