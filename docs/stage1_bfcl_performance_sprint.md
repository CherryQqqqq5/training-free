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

Until the scorer evidence exists, the repository status remains:

- Engineering scaffold: ready for diagnostic handoff.
- Formal BFCL performance acceptance: not ready.

## Critical Path

1. Provider green preflight.
2. Frozen BFCL acceptance protocol.
3. Deterministic argument/tool-use repair candidate pool of at least 35 usable
   demote candidates.
4. Non-overlapping dev20 and holdout20 manifests.
5. Same-protocol baseline and candidate BFCL scorer runs.
6. Paired comparison with accuracy, cost, latency, and regression accounting.
7. SOTA or Huawei baseline comparison proving the required 3% improvement.

## P0 Blockers

- Valid provider credentials are required before source collection or scorer
  execution.
- The current provider preflight is red: OpenRouter and Novacode attempts are
  blocked by HTTP 401 class failures.
- M2.8-pre offline gate must pass before scorer authorization.
- Baseline and candidate run manifests must align on BFCL version, model,
  provider, split/category, evaluator, decoding config, and tool schema.
- No performance claim is allowed before paired BFCL scorer artifacts exist.

## Owner Split

- Huawei acceptance owner: freeze provider, BFCL split/full-suite scope, SOTA or
  accepted baseline source, and +3pp calculation unit.
- Algorithm owner: expand deterministic argument/tool-use repair candidates,
  prioritizing explicit required-argument literal completion before zero-coverage
  families.
- Engineering owner: make provider preflight green, run source collection,
  build dev/holdout manifests, execute paired baseline/candidate scorer runs,
  and generate the formal comparison artifacts.

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
