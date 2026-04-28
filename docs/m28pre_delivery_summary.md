# M2.8-pre Delivery Summary

This document is the canonical first-stage handoff status for the current `training-free` repository state.

## Claim Boundary

The current repository should be delivered as a **training-free self-evolution scaffold and diagnostic evidence package**, not as a completed BFCL performance proof.

Allowed claim:

- The project has implemented a trace-to-rule scaffold for training-free tool-use repair.
- The M2.7 CTSPC-v0 line was audited, found net-negative on dev scorer evidence, and frozen as diagnostic-only.
- The M2.8-pre line moved retention from benchmark-driven rule mining to theory-guided retention priors.
- Offline gates currently fail closed and do not authorize scorer, holdout, 100-case, M2.8, or full BFCL.

Disallowed claim:

- Do not claim a complete self-evolving agent has been performance-validated.
- Do not claim CTSPC-v0 improves BFCL.
- Do not claim any rule is retained memory.
- Do not claim M2.8-pre is scorer-ready.

## Current Evidence Snapshot

Latest pushed baseline before this delivery hardening: `a85d2406`.

M2.7 CTSPC-v0:

- Status: `diagnostic_experimental`.
- Runtime default: off for scorer.
- Retain count: `0`.
- Latest durable dev scorer evidence was negative; this line is frozen for diagnostic use.

M2.8-pre theory-prior pool:

- `explicit_required_arg_literal_completion`: 17 demote candidates.
- `wrong_arg_key_alias_repair`: 0 demote candidates, coverage audit complete.
- `deterministic_schema_local_non_live_repair`: 0 demote candidates, coverage audit complete.
- Combined retain-eligible candidates: 17.
- Required threshold before scorer planning: 35 plus valid dev20/holdout20 split.
- `scorer_authorization_ready=false`.
- `m2_8pre_offline_passed=false`.

## Theory-Guided Retention Policy

The M2.8-pre retention policy is theory-first:

1. A rule family must satisfy a retention prior before BFCL score is considered.
2. BFCL score cannot create a retain rule.
3. Missing `retention_prior` defaults to `never_retain`.
4. Dev evidence can at most support demotion/diagnostics before holdout.
5. Holdout scorer evidence is required before any retained memory claim.

Current retain-prior families:

- `explicit_required_arg_literal_completion`
- `wrong_arg_key_alias_repair`
- `deterministic_schema_local_non_live_repair`

Only the explicit literal family currently has non-zero coverage.

## Delivery Gates

The delivery boundary now has two different modes:

- Summary mode: writes compact artifacts even when a gate fails.
- Strict gate mode: exits non-zero when a delivery gate is false.

Required local verification commands:

```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -m pytest -q
PYTHONPATH=.:src .venv/bin/python scripts/check_m28pre_offline.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_artifact_boundary.py
PYTHONPATH=.:src .venv/bin/python scripts/audit_delivery_evidence.py --compact
```

Expected current behavior:

- Full pytest should pass in the managed `.venv` environment.
- `check_m28pre_offline.py --strict` should fail until M2.8-pre reaches scorer authorization readiness.
- `check_artifact_boundary.py` should fail if raw traces, BFCL result/score trees, logs, `.env`, `repairs.jsonl`, or repair records are present under `outputs/`.

## Current Blockers

P0 blockers before first-stage acceptance as a complete self-evolution system:

- No accepted/retained rule with dev + holdout evidence.
- M2.8-pre combined retain-eligible candidate count is below threshold.
- Wrong-key alias and deterministic schema-local families have zero current coverage.
- Server output tree contains raw/secret/repair artifacts that must remain outside the committed delivery package.

## Next Work

The next engineering step should be evidence-driven root-cause analysis, not another scorer run.

Priority:

1. Use compact artifacts and source-result layout audits to decide whether zero coverage is a parser/source-layout issue or true family mismatch.
2. If it is an implementation issue, fix parser/extractor and rerun offline audits only.
3. If it is an algorithm or benchmark/source-layout issue, discuss the theory family with delivery review and research review before changing the compiler.
4. Do not weaken retention priors to inflate candidate counts.

## Explicit Non-Authorization

This document does not authorize:

- BFCL/model/scorer runs.
- Holdout scorer runs.
- 100-case or full BFCL.
- M2.8 formal performance evaluation.
- Retained memory claims.
