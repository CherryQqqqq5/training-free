# Stage-1 BFCL Performance Sprint

This document is the execution plan for the formal Stage-1 performance
acceptance path. It does not change the Huawei requirement: the final delivery
needs reproducible BFCL/HLE benchmark evidence, not only scaffold readiness.

## Target Claim

The only acceptable Stage-1 performance claim is:

> Under a fixed BFCL protocol, fixed model/provider route, fixed benchmark
> split, and unmodified BFCL evaluator, the GRC-patched candidate improves over
> the accepted same-scale baseline/SOTA reference by at least the required 3%
> threshold without unacceptable regressions.

Current status after the Stage-1 deterministic-family diagnostics:

- Provider technical preflight: green for Chuangzhi/Novacode, profile
  `novacode`, model `gpt-5.2`.
- Provider green is a technical route check only. It does not authorize scorer,
  candidate, paired-comparison, SOTA, or Huawei acceptance claims.
- Current blocker: deterministic Stage-1 family search exhausted / zero-yield,
  not provider credential access.
- Formal BFCL performance acceptance: not ready.

## Critical Path

1. Provider green preflight. Current technical preflight is green for
   Chuangzhi/Novacode `gpt-5.2`, but this is not scorer authorization.
2. Frozen BFCL acceptance protocol.
3. Deterministic argument/tool-use repair candidate pool of at least 35 usable
   demote candidates. Current deterministic families are zero-yield under the
   approved gates, so this step is blocked pending scope-change review.
4. Non-overlapping dev20 and holdout20 manifests.
5. Same-protocol baseline and candidate BFCL scorer runs.
6. Paired comparison with accuracy, cost, latency, and regression accounting.
7. SOTA or Huawei baseline comparison proving the required 3% improvement.

## P0 Blockers

- Deterministic Stage-1 family search is exhausted under current evidence:
  explicit required-arg literal, wrong-key alias, schema-local non-live,
  structural malformed/final-before-tool, raw tool-name/schema normalization,
  and schema retrieval/rerank feasibility all returned zero-yield or stop-gate
  outcomes.
- Candidate pool is not ready: `candidate_pool_ready=false`.
- Scorer is not authorized: `scorer_authorized=false`.
- Performance evidence is absent: `performance_evidence=false`.
- SOTA/+3pp and Huawei acceptance claims are forbidden until a separately
  authorized candidate pool, scorer chain, and paired comparison exist.
- M2.8-pre offline gate must pass before any scorer authorization.
- Baseline and candidate run manifests must align on BFCL version, model,
  provider, split/category, evaluator, decoding config, and tool schema.
- No performance claim is allowed before paired BFCL scorer artifacts exist.

## Owner Split

- Huawei acceptance owner: freeze provider, BFCL split/full-suite scope, SOTA or
  accepted baseline source, and +3pp calculation unit if a new scope is
  authorized.
- Algorithm owner: decide whether the zero-yield negative evidence supports a
  scope change. Continuing the deterministic candidate-pool sprint is not
  currently authorized by the evidence.
- Engineering owner: preserve the fail-closed evidence chain and implement only
  approved scope-change or audit tasks. Do not run scorer/source expansion or
  promote candidates without explicit authorization.

## Formal Artifacts

Expected performance acceptance artifacts:

```text
outputs/bfcl_runs/baseline/<run_id>/
  run_manifest.json
  metrics.json
  score.json
  sanitized_summary.json

outputs/bfcl_runs/candidate/<run_id>/
  run_manifest.json
  metrics.json
  score.json
  sanitized_summary.json
  active_rules_snapshot.yaml

outputs/artifacts/stage1_bfcl_acceptance/
  paired_comparison.json
  regression_report.json
  cost_latency_report.json
  acceptance_decision.json
  performance_ready.json
  performance_ready.md
```

Raw BFCL result/score trees, traces, logs, `.env`, `repairs.jsonl`, and repair
records must stay outside the committed delivery package.

## Mandatory Gates

```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest -q
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
PYTHONPATH=.:src .venv/bin/python scripts/check_provider_green_preflight.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_m28pre_offline.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_bfcl_paired_comparison.py --acceptance-root outputs/artifacts/stage1_bfcl_acceptance --provider-status outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_stage1_bfcl_performance_ready.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_first_stage_bfcl_ready.py --compact --strict
```

`check_first_stage_bfcl_ready.py` is allowed to report scaffold handoff status.
`check_stage1_bfcl_performance_ready.py` is the formal performance acceptance
gate and must remain fail-closed until BFCL scorer evidence exists.

Current fail-closed frontier: `candidate_pool_ready=false`,
`scorer_authorized=false`, `performance_evidence=false`,
`sota_3pp_claim_ready=false`, and `huawei_acceptance_ready=false`.
