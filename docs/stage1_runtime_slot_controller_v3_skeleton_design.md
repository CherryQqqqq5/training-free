# Stage1 ABHE-v0 runtime_slot_controller_v3 skeleton — design

Status: `skeleton-only` on feature branch `feat/runtime-slot-controller-v3`.
This document does NOT claim performance, +3pp, Huawei acceptance, or any
scorer/holdout/full-suite evidence. `runtime_wired_into_proxy = false`.

## What v3 skeleton is

A **deterministic, fixture-driven composer** over the existing v2
primitives in `scripts/abhe_v0_runtime_slot_controller.py`:

1. `required_arg_schema_reader_v0`
2. `valid_tool_call_guard_v0`
3. `prior_tool_observation_slot_binder_v0`
4. `prerequisite_lookup_planner_v0`

For each synthetic case in
`tests/fixtures/abhe_runtime_slot_controller_v3_skeleton/cases.json`,
the composer records a per-case decision trace covering:
- schema_read summary (required-arg count + names)
- guard outcome (valid? missing? incompatible?)
- binder outcome (bound slots + sources, ambiguous slots, missing-after-bind)
- planner outcome (planned lookup tools, unrecoverable slots)
- final decision (one of 5 deterministic classes)

The output artifact
`outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_v3_skeleton.json`
is fail-closed: any non-whitelisted key, any forbidden substring, any
attestation drift, any case mismatch, fails the strict builder and the
strict checker.

## What v3 skeleton is NOT

- NOT wired into the proxy request/response path
- NOT exercised against any real BFCL case
- NOT a scorer
- NOT a provider call
- NOT a candidate generator
- NOT a holdout / full-suite touchpoint
- NOT performance / +3pp / Huawei evidence

The next phase (`runtime_slot_controller_v3_wired`) requires:
1. an approved rerun packet (P1.5b)
2. integration into the BFCL proxy
3. provider stability (C3)
4. machine-verified bind-repair count > 0 on a bounded dev slice

## Why this design

Literature (web research, 2025):

- **Reinforced Agent (2025)**: an inference-time *reviewer* evaluates
  provisional tool calls *prior to execution*. Our composer is a fail-closed
  offline analog: it reviews a synthetic provisional call before any
  execution and emits a deterministic decision class.
- **ToolWeave (2025)**: emphasises *parameter provenance tracking* to
  reduce argument hallucination. Our composer records
  `binder_bound_slot_sources` per case.
- **BFCL-v3 blog (Berkeley, 2024)**: missing-parameter category is
  intentionally state-based — the correct behaviour is either ask-user or
  call a prerequisite-lookup tool to recover the slot from backend state.
  Our decision-class taxonomy matches this exactly.
- **Tool Calling is Linearly Readable (2025)**: small top-1 / top-2
  tool-name gap predicts 14-21x higher error rates. Motivates explicit
  ambiguity recording in the binder, which we already capture via
  `binder_entity_ambiguity_detected`.
- **EigenData (2025)**: BFCL-v3 itself has schema / trajectory errors;
  state-based eval is preferred over turn-level matching. We treat this
  as a known measurement risk — our skeleton stays compact and does NOT
  commit raw trajectories.

## Boundary invariants (must remain True across all promotions)

- `runtime_wired_into_proxy = False` until P1.5b is approved AND a wired
  rerun produces machine-verified bind repairs.
- All raw-material attestations False.
- All performance / acceptance attestations False.
- Forbidden substrings: `prompt`, `gold`, `expected_argument`,
  `argument_value`, `raw_response`, `raw_payload`, `scorer_diff`.
- Attestation allowlist: 9 explicit keys (see builder header).

## Files added on this branch

- `scripts/build_abhe_v0_runtime_slot_controller_v3_skeleton.py`
- `scripts/check_abhe_runtime_slot_controller_v3_skeleton_ready.py`
- `tests/test_abhe_v0_runtime_slot_controller_v3_skeleton.py`
- `tests/fixtures/abhe_runtime_slot_controller_v3_skeleton/cases.json`
- `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_runtime_slot_controller_v3_skeleton.json`
- `docs/stage1_runtime_slot_controller_v3_skeleton_design.md`
- `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_p1_5b_per_case_scorer_slicer_approval_packet_draft.md`

## Pre-merge gate (must all hold)

- 6 ABHE core checkers: 5 exit 0 + 1 by-design fail-closed (unchanged from main)
- 9 ABHE gate test files: 65 pass (unchanged from main)
- new v3 skeleton checker: exit 0
- new v3 skeleton tests: 11 pass
- working tree clean post-test (commit-time `git checkout --` discipline)
