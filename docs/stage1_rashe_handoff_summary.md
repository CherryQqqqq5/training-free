# Stage-1 RASHE Offline Scaffold Handoff Summary

This handoff summarizes the Stage-1 RASHE route at the current offline scaffold boundary. It is not a BFCL performance claim, not a SOTA/+3pp claim, and not a Huawei acceptance claim.

## Current State

RASHE is the active approved Stage-1 scope-change route. The current deliverable is an offline, fail-closed scaffold for training-free skill-harness research.

Current state:

- RASHE offline scaffold is ready for handoff review.
- BFCL +3pp is not ready.
- Candidate pool is not ready.
- Runtime behavior is not authorized.
- Source/real trace use is not authorized.
- Candidate generation is not authorized.
- Scorer/dev/holdout/full BFCL evaluation is not authorized.
- Performance, SOTA, and Huawei acceptance claims are not authorized.

The offline scaffold can validate schemas, fixtures, router decisions, proposal drafts, and evolution-loop metadata. It cannot affect prompts, retry behavior, tool execution, candidate generation, scorer execution, or BFCL result claims.

## Completed Offline Assets

The following assets are complete for the offline scaffold boundary:

- RASHE scope approval packet.
- Default-disabled inert runtime skeleton.
- StepTraceBuffer v0.2 schema and checker.
- Seed SkillBank metadata and router gates.
- Forbidden evidence taxonomy for seed skills and proposal drafts.
- Router decision schema aligned with the observed decision surface.
- Proposal draft schema for inert skill metadata, progressive disclosure, and router policy drafts.
- Offline evolution loop design and checker.
- Offline scaffold readiness checker.
- Active evidence index refresh covering RASHE scaffold state and deterministic negative evidence.

Core commands currently represented by the scaffold:

- `scripts/check_rashe_runtime_skeleton.py --compact --strict`
- `scripts/check_rashe_step_trace_buffer.py --compact --strict`
- `scripts/check_rashe_skill_metadata.py --compact --strict`
- `scripts/check_rashe_proposer_schema.py --compact --strict`
- `scripts/check_rashe_evolution_loop.py --compact --strict`
- `scripts/check_rashe_offline_scaffold_ready.py --compact --strict`

These commands check offline scaffold integrity only. Passing them does not imply BFCL performance readiness.

## Negative Deterministic Evidence

The previous deterministic Stage-1 search should remain closed unless a new, separately approved scope change reopens it. The active negative evidence says the following paths are zero-yield under their approved diagnostics:

- `explicit_required_arg_literal_completion`
- `wrong_arg_key_alias_repair`
- `deterministic_schema_local_non_live_repair`
- structural malformed/final-before-tool attribution
- raw tool-name/schema normalization
- schema retrieval/rerank feasibility

Mechanical source expansion and same-pilot family hunting should remain stopped. These negative diagnostics explain the move to RASHE, but they are not performance evidence.

## Current Prohibitions

The following actions remain forbidden without separate approval:

- runtime behavior changes
- prompt injection
- retry behavior
- source collection or real-trace ingestion
- candidate generation
- candidate pool promotion
- candidate JSONL or repair rule emission
- dev manifest or holdout manifest creation
- BFCL scorer runs
- paired baseline/candidate comparison
- full BFCL suite execution
- performance, SOTA/+3pp, or Huawei acceptance claims

The scaffold also forbids use of raw case identifiers, raw trace text, raw provider payloads, gold, expected answers, scorer diffs, candidate outputs, repair outputs, holdout feedback, or full-suite feedback for skill writing, proposal generation, routing thresholds, or metadata patch plans.

## Required Separate Approval Packets

Any work beyond the offline scaffold needs a separate approval packet. The approval lanes must remain distinct:

1. Runtime behavior approval before any router decision, skill, proposal, or metadata patch can affect prompts, retries, tools, execution paths, or RuleEngine/proxy behavior.
2. Source/real-trace approval before any real trace, provider payload, raw response, or non-synthetic compact record is collected, transformed, committed, or used.
3. Candidate/proposer execution approval before any proposal is executed as a candidate, any candidate JSONL is emitted, or any repair rule/dev/holdout manifest is created.
4. Scorer/dev/holdout/full approval before any BFCL baseline/candidate scoring, paired comparison, dev split, holdout split, or full-suite run.
5. Performance/+3pp/Huawei acceptance approval before any SOTA, +3pp, formal BFCL performance, or Huawei acceptance claim is made.

Each approval packet must restate no-leakage boundaries, allowed inputs, forbidden sources, stop conditions, counters, cost/latency/regression expectations when applicable, and rollback behavior.

## Recommended Next Step

The next recommended step is to prepare the relevant approval packet before running anything new.

Do not directly start runtime behavior, source collection, candidate generation, scorer execution, dev/holdout construction, or full BFCL evaluation from the offline scaffold. The scaffold is a readiness and handoff boundary, not an execution authorization.

Recommended immediate path:

1. Choose the next lane: runtime behavior, source/real trace, candidate/proposer execution, scorer protocol, or performance acceptance.
2. Write a narrow approval packet for that lane.
3. Review no-leakage, overfitting, cost/latency, regression, and rollback constraints.
4. Only after explicit approval, implement the smallest corresponding executable increment.

Until then, the correct claim is: RASHE offline scaffold ready; BFCL +3pp not ready.
