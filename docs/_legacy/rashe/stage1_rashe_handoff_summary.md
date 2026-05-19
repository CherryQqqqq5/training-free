# Stage-1 RASHE Handoff Summary

This handoff summarizes the Stage-1 RASHE route after L1 runtime behavior approval. It is not a BFCL performance claim, not a SOTA/+3pp claim, and not a Huawei acceptance claim.

## Current State

RASHE is the active approved Stage-1 scope-change route. The offline scaffold is present and fail-closed, and L1 runtime behavior is approved only for synthetic/default-disabled wiring.

Current state:

- RASHE offline scaffold is ready for handoff review.
- Runtime L1 is approved only for `synthetic_default_disabled_only` checks.
- `configs/runtime_bfcl_skills.yaml` remains `enabled=false` by default.
- BFCL +3pp is not ready.
- Candidate pool is not ready.
- Source/real trace use is not authorized.
- Candidate generation is not authorized.
- Scorer/dev/holdout/full BFCL evaluation is not authorized.
- Performance, SOTA, and Huawei acceptance claims are not authorized.

The L1 runtime approval allows only synthetic/default-disabled runtime behavior tests. It does not authorize provider calls, source collection, candidate generation, scorer execution, dev/holdout/full BFCL, or performance claims.

## Completed Assets

The following assets are complete for the current boundary:

- RASHE scope approval packet.
- Default-disabled inert runtime skeleton.
- L1 runtime behavior approval packet for `synthetic_default_disabled_only`.
- Post-runtime behavior approval checker.
- Post-runtime approval review matrix checker.
- Post-runtime main readiness checker.
- StepTraceBuffer v0.2 schema and checker.
- Seed SkillBank metadata and router gates.
- Forbidden evidence taxonomy for seed skills and proposal drafts.
- Router decision schema aligned with the observed decision surface.
- Proposal draft schema for inert skill metadata, progressive disclosure, and router policy drafts.
- Offline evolution loop design and checker.
- Active evidence index refresh covering RASHE scaffold state, L1 runtime approval, and deterministic negative evidence.

Core commands represented by the current boundary:

- `scripts/check_rashe_runtime_behavior_approved.py --compact --strict`
- `scripts/check_rashe_approval_packet_review_matrix_after_runtime_behavior.py --compact --strict`
- `scripts/check_rashe_main_merge_readiness_after_runtime_behavior.py --compact --strict`
- `scripts/check_rashe_runtime_skeleton.py --compact --strict`
- `scripts/check_rashe_step_trace_buffer.py --compact --strict`
- `scripts/check_rashe_skill_metadata.py --compact --strict`
- `scripts/check_rashe_proposer_schema.py --compact --strict`
- `scripts/check_rashe_evolution_loop.py --compact --strict`

These commands check post-runtime approval consistency and offline scaffold integrity only. Passing them does not imply BFCL performance readiness.

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

The following actions remain forbidden without separate downstream approval:

- runtime enabled by default
- prompt injection into real BFCL requests
- retry behavior on real BFCL responses
- source collection or real-trace ingestion
- provider calls
- candidate generation
- candidate pool promotion
- candidate JSONL or repair rule emission
- dev manifest or holdout manifest creation
- BFCL scorer runs
- paired baseline/candidate comparison
- full BFCL suite execution
- performance, SOTA/+3pp, or Huawei acceptance claims

The boundary also forbids use of raw case identifiers, raw trace text, raw provider payloads, gold, expected answers, scorer diffs, candidate outputs, repair outputs, holdout feedback, or full-suite feedback for skill writing, proposal generation, routing thresholds, or metadata patch plans.

## Approval Lanes

The runtime behavior lane is now L1 approved for `synthetic_default_disabled_only`. The four downstream lanes remain pending and fail-closed:

1. Source/real-trace approval before any real trace, provider payload, raw response, or non-synthetic compact record is collected, transformed, committed, or used.
2. Candidate/proposer execution approval before any proposal is executed as a candidate, any candidate JSONL is emitted, or any repair rule/dev/holdout manifest is created.
3. Scorer/dev/holdout/full approval before any BFCL baseline/candidate scoring, paired comparison, dev split, holdout split, or full-suite run.
4. Performance/+3pp/Huawei acceptance approval before any SOTA, +3pp, formal BFCL performance, or Huawei acceptance claim is made.

Each downstream approval packet must restate no-leakage boundaries, allowed inputs, forbidden sources, stop conditions, counters, cost/latency/regression expectations when applicable, and rollback behavior.

## Recommended Next Step

The next recommended engineering step is to write synthetic/default-disabled runtime behavior tests only. Do not start source collection, provider calls, candidate generation, scorer execution, dev/holdout construction, or full BFCL evaluation from this approval.

Until further downstream approvals, the correct claim is: RASHE offline scaffold ready; runtime L1 approved only for synthetic/default-disabled behavior checks; BFCL +3pp not ready.
