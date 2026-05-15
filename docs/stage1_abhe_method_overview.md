# Stage-1 ABHE Method Overview

Status: planning and approval-packet stage only. This document does not authorize source collection, provider calls, candidate generation, candidate JSONL, BFCL scorer execution, dev/holdout/full BFCL, paired comparison, performance evidence, +3pp claims, SOTA claims, or Huawei acceptance claims.

## Method

ABHE means Archive-Based Behavior Harness Evolution.

ABHE upgrades the Stage-1 route from a scaffold-centered RASHE narrative to an archive-centered behavior evolution loop. The archive is the decision center. It records observed behavior-level failure clusters, compact evidence mass, coverage strata, mechanism hypotheses, risk flags, recommended actions, development feedback history, and state transitions.

RASHE remains retained as discovery scaffold evidence. It is not the current complete method and it is not an immediate scorer route.

## Evidence Boundary

The 160 compact source cases are discovery evidence only. They may be used for:

- failure discovery
- behavior clustering
- archive seeding
- opportunity triage

They must not be used for:

- performance improvement claims
- candidate validation
- paired baseline/candidate claims
- +3pp claims

Any dev smoke must use a fresh dev slice and a paired baseline/candidate comparison after a separate execution packet is approved.

## Objects

BFCL categories are sampling, reporting, and validation strata only. They are not archive candidates.

Valid ABHE archive candidates are behavior-level entries such as:

- `state_tracking_v0`
- `hallucination_abstain_v0`
- `unresolved_search_memory_watch_v0`

Invalid mainline narratives include direct category-to-skill mappings such as:

- `multi_turn` category becomes one skill
- `hallucination` category becomes one skill
- `live` category becomes one skill
- `memory` category becomes one skill

The behavior cluster is the unit of evolution. For example, `multi_turn_state_lost` is a candidate cluster; `multi_turn` is only a stratum.

## Current ABHE Decision

The current archive decision is:

1. `state_tracking_v0`: request a bounded dev smoke after approval.
2. `hallucination_abstain_v0`: request a bounded dev smoke after approval.
3. `unresolved_search_memory_watch_v0`: keep watch status and split or collect more compact diagnostics.

The search/memory watch entry must not enter scorer as a single mixed mechanism. It must first split into `search_query_or_fetch_failure` and `memory_retrieve_update_confusion`, and each child cluster needs cross-strata evidence or a reviewer-approved bounded exception before it can become `proposal_ready`.

## Two-Stage Loop

Pre-dev answers only one question:

Which archive entry is worth requesting for fresh bounded dev smoke?

Post-dev answers a different question:

Should the candidate be retained, split, narrowed, demoted, or rejected?

These stages must not be collapsed. A pre-dev plan is not validation evidence.

## Fresh Dev Smoke Gate

Fresh bounded dev smoke must be separately approved and pre-registered with:

- baseline command
- candidate command
- case list hash
- fresh dev slice source
- provider, model, and protocol
- runtime config
- candidate rule path
- artifact boundary
- cost and latency cap
- regression cap
- stop-loss criteria

ABHE proposes bounded dev smoke. It does not authorize execution by itself.

## Trace And Dev Packets

The next explanatory packet and the next validation packet are separate:

1. Temporary trace extraction approval packet: explains mechanism with sanitized trace cards.
2. ABHE bounded dev smoke execution packet: validates a candidate on a fresh dev slice.

Trace cards are explanatory evidence, not performance evidence. They must not change archive entries to `dev_passed`.

## Post-Dev State Updates

After an approved fresh dev smoke, update archive entries with:

- `target_bucket_reduction`
- `fixed_count`
- `regressed_count`
- `net_fixed`
- `non_target_regression_count`
- `activation_precision`
- `activation_recall`
- `cost_delta_pct`
- `latency_delta_pct`
- `leakage_count`
- `boundary_violation_count`

Hard transition rules:

- `leakage_count > 0` -> `rejected_boundary_failure`
- `target_bucket_reduction <= 0` -> `demoted_no_mechanism_signal`
- `fixed_count <= regressed_count` -> `demoted_regression_not_controlled`
- high non-target regression -> `narrow_router_requested`
- mixed strata result -> `split_requested`
- target bucket down, fixed greater than regressed, and cost acceptable -> `dev_passed`

