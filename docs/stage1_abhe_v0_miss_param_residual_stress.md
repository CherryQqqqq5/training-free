# Stage 1 ABHE-v0 Miss-Param Residual Stress

This stage is a targeted bounded dev smoke, not full BFCL and not holdout.
It starts from the fresh-slice finding that frozen_v2 generalizes while
multi_turn_miss_param remains the main residual bottleneck.

## Scope

The slice overweights multi_turn_miss_param and keeps compact regression
controls for multi_turn_miss_func, multi_turn_base, multi_turn_long_context,
irrelevance, and live_irrelevance. live_relevance is not forced here because
available non-overlapping fresh rows have already been exhausted by prior dev
slices.

## Arms

- baseline
- frozen_v2
- slot_recovery_v1: frozen v2 plus missing_param_slot_recovery_controller_v1

post_tool_continuation_guard_v0 and no_tool_boundary_v0 are frozen. The old
missing_param_epistemic_gate_v0 is treated as no-independent-signal evidence.
long_context_state_retrieval_v0 remains narrowed due prior non-target regression.

## Evidence Boundary

All committed artifacts are compact-only. They contain compact identifiers,
hashes, scorer-unit summaries, and sanitized taxonomy labels. Disallowed
benchmark/provider materials are absent from committed artifacts. Archive updates
remain dry-run and performance_evidence remains false.
