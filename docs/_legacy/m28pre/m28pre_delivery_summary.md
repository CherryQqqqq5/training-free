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

Latest status: memory-operation offline workflow and runtime adapter readiness are present; BFCL smoke remains unexecuted and requires separate explicit approval.

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

Only the explicit literal family currently has non-zero coverage in the argument-repair pool.

## Memory Operation Obligation Line

A separate theory-prior family has been added for memory-operation self-evolution. This line is still offline-only, but it now demonstrates a complete dry-run workflow:

1. `memory_operation_obligation` audit finds retrieve obligations where a user asks for memory-backed information and no strong memory value witness is present.
2. Negative controls are evaluated with non-zero denominators, using synthetic controls only when the current source pool has no strong/delete examples.
3. A sanitized approval manifest is produced for review; it keeps `compiler_input_eligible_count=0` and excludes trace paths, case ids, raw prompts/outputs, available tool lists, scorer/gold fields, and repair records.
4. A separate compiler allowlist contains only first-pass `no_witness` records; weak lookup witnesses remain excluded and require separate approval.
5. A dry-run policy unit, `memory_first_pass_retrieve_soft_v1`, is compiled from the allowlist only. It is guidance-only, capability-only, argument-free, `exact_tool_choice=false`, and `runtime_enabled=false`.
6. A schema-local resolver audit projects memory capability families onto available memory tools while blocking mutation tools.
7. A runtime-like activation simulation confirms activation only for first-pass supported records and zero activation for negative controls.

Current compact evidence:

- Memory obligation candidates: `78`.
- First-pass compiler allowlist records: `48`.
- Weak witness compiler inputs: `0`.
- Dry-run policy units: `1`.
- Resolver scanned/resolved schemas: `48 / 48`.
- Destructive memory tools blocked by resolver: `288`.
- Forbidden mutation tools resolved: `0`.
- Activation simulation count: `48`.
- Negative-control activation count: `0`.
- Argument creation count: `0`.

This is stronger workflow evidence for a training-free self-evolution loop, but it is not BFCL performance evidence and does not authorize runtime/scorer use.


## Memory Smoke Readiness Update

The memory-operation line now has an explicit fail-closed readiness check for a future small dev smoke:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_memory_operation_runtime_smoke_readiness.py --compact
```

Current state after adapter compilation is smoke-ready but not scorer-authorized:

```text
memory_runtime_adapter_ready = true
memory_dev_smoke_ready = true
loaded_memory_runtime_rule_count = 1
next_required_action = request_separate_memory_only_dev_smoke_approval
```

The adapter resolves the earlier engineering blocker: the BFCL patch runner can load a runtime `Rule` YAML rather than metadata-only `policy_unit.yaml`. A memory-only smoke still requires a separate explicit approval, fixed case list, 创智/novacode provider, and preregistered baseline/candidate commands.

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
- No BFCL scorer evidence for the memory-operation dry-run policy.
- M2.8-pre argument-repair combined retain-eligible candidate count is below threshold.
- Wrong-key alias and deterministic schema-local families have zero current coverage.
- Artifact boundary is now clean in the current checkout; raw traces, BFCL
  result/score trees, logs, `.env`, `repairs.jsonl`, and repair records must
  remain outside the committed delivery package.

## Next Work

The next engineering step should be evidence-driven root-cause analysis, not another scorer run.

Priority:

1. Keep the memory-operation line offline until delivery/research review approves a memory-only dev scorer plan.
2. If approved later, run only a memory-only dev scorer gate using the same base model and compare baseline vs `memory_first_pass_retrieve_soft_v1`; do not run holdout until dev passes.
3. For the argument-repair M2.8-pre pool, use compact artifacts and source-result layout audits to decide whether zero coverage is a parser/source-layout issue or true family mismatch.
4. If it is an implementation issue, fix parser/extractor and rerun offline audits only.
5. If it is an algorithm or benchmark/source-layout issue, discuss the theory family with delivery review and research review before changing the compiler.
6. Do not weaken retention priors to inflate candidate counts.

## Explicit Non-Authorization

This document does not authorize:

- BFCL/model/scorer runs.
- Holdout scorer runs.
- 100-case or full BFCL.
- M2.8 formal performance evaluation.
- Retained memory claims.
