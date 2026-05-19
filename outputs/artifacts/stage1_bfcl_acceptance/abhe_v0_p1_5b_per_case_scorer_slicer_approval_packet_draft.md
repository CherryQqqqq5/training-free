# ABHE-v0 P1.5b — per-case scorer slicer rerun — APPROVAL PACKET (DRAFT, NOT APPROVED)

Status: **`draft_not_approved`** — this packet is checked-in for review only.
It does **not** authorize any provider call, BFCL rerun, scorer call,
holdout touch, full-suite touch, archive update, performance claim,
+3pp claim, or Huawei acceptance.

`approval_status = draft_not_approved` until a human review countersigns
the rerun scope.

## Why P1.5b is needed (honest finding rooted in machine-verified state)

P1's machine-verified result (commit `9039bb04`, `3d09c6ce`):
```
abhe_v0_true_per_selected_id_score_adapter.json
  target_category = multi_turn_miss_param
  target_promoted_direct_count = 0
  target_total_count = 24
  promotion_blocker = "scorer_unit_covers_multiple_selected_cases"
  abhe_score_output_contract_satisfied = false
```

I.e. 24 multi_turn_miss_param selected cases are collapsed into the
same scorer-unit aggregates per arm. No per-case independent pass
signal exists on disk. The promotion rule "scorer-unit covers exactly
one selected compact case" is honest but unsatisfiable with current
tmp traces (which are also gone from disk:
`bfcl_evaluate_called=False`, `scorer_called=False` in current
diagnostic).

P1.5b's mechanism is **per-case scorer invocation slicing**: invoke
the BFCL scorer separately for each selected compact case so that
each scorer_unit aggregates exactly one selected case. This makes the
P1 promotion rule satisfiable for the target category without any
scorer-source modification.

This **requires a bounded BFCL generate + evaluate rerun** because the
tmp trace material was never persisted (correctly — boundary
discipline) and cannot be reconstructed offline.

## Proposed scope (the actual ask under review)

Field | Value
---|---
`approval_scope` | `per_case_scorer_slicer_bounded_residual_dev_smoke_only`
`approved_selected_case_ids_hash` | TBD by reviewer at signing
`approved_selected_case_count` | 48 (same compact slice as P1)
`approved_target_category` | `multi_turn_miss_param`
`approved_target_selected_compact_case_count` | 24
`approved_target_unique_scorer_unit_count` | **24** (post-slicing; currently 1)
`approved_target_compact_to_scorer_unit_factor` | **1.0** (post-slicing)
`approved_provider` | `ToolCallingFunction/OpenAICompatible`
`approved_profile` | `toolcallingfunction`
`approved_model` | `gpt-4.1`
`approved_route_policy` | `toolcallingfunction_openai_compatible_only_openrouter_disabled`
`approved_protocol` | `bfcl_v4_abhe_v0_per_case_scorer_slicer_bounded_residual_dev_smoke_toolcallingfunction`
`approved_arms` | `["baseline", "conditional_frozen_v2", "runtime_slot_controller_v2"]`

## Required-true booleans

- `authorized = true`
- `provider_calls_authorized = true`
- `bfcl_generate_authorized = true`
- `bfcl_evaluate_authorized = true`
- `scorer_authorized = true` (per-case slicer mode only)
- `per_case_scorer_invocation_authorized = true` (NEW)

## Forced-false booleans (boundary discipline)

- `holdout_authorized = false`
- `full_suite_authorized = false`
- `archive_update_authorized = false`
- `performance_claim_authorized = false`
- `performance_evidence = false`
- `sota_3pp_claim_ready = false`
- `huawei_acceptance_ready = false`
- `raw_outputs_committed = false`
- `raw_provider_payload_committed = false`
- `raw_bfcl_result_tree_committed = false`
- `gold_expected_committed = false`
- `scorer_diff_committed = false`
- `prompt_literal_committed = false`
- `argument_values_committed = false`

## Required stop-loss triggers (any → halt + revoke)

- `raw_leakage`
- `provider_model_protocol_mismatch`
- `case_list_hash_mismatch`
- `scorer_unit_alignment_mismatch` (must verify post-rerun:
  `unique_scorer_unit_count == selected_case_count` for target category)
- `runner_manifest_incompatible`
- `runtime_config_missing_or_mismatch`
- `cost_latency_cap_exceeded`
- `regression_cap_exceeded` (no arm worse than baseline by more than X — X
  to be set at signing; suggested: error_class delta cap of 2 cases per arm)
- `scorer_artifact_schema_failure`
- `per_case_scorer_call_count_mismatch` (NEW: must be ≥ 24 distinct
  scorer invocations for target category; signed at the manifest level)
- `provider_504_rate_exceeded` (NEW: C3 risk — cap at e.g. 5%; if
  exceeded, halt and switch to P3 backoff before retrying)

## Outputs allowed by this packet (compact-only)

- `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_rerun_manifest.json`
- `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_arm_compact.json`
  (one per arm; aggregate-only counts; no raw trace; no prompt; no gold;
  no expected; no argument values)
- `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_per_case_scorer_slicer_post_promotion_score_adapter.json`
  (rerun of P1's adapter against new slicer output; expected to satisfy
  the contract for the target category if the slicer worked)

## Forbidden material (unchanged from prior packets)

Raw prompt, raw trace, provider request/response, case ID literal,
gold, expected, reference, scorer diff, candidate output, repair
feedback, holdout/full feedback, endpoint/key material, source nonce
mapping.

## Pre-rerun dependencies (must hold before signing)

1. P2 v3 skeleton merged (`feat/runtime-slot-controller-v3` merged into
   `stage1-bfcl-performance-sprint`) **OR** demonstrated indifference
   (P1.5b can run on baseline + conditional_frozen_v2 arms alone if v3
   is not yet wired).
2. P3 provider stability characterization committed (C3 risk).
3. Same case-id hash as P1 (`9b26ba3d24...` per existing
   `distinct_rerun_approval_packet`) — verified by reviewer at signing.

## Pre-rerun honest-expectation note

Even if the slicer works:

- The contract probe will become satisfiable for `multi_turn_miss_param`.
- This does **not** mean any arm beats baseline. It only means the
  measurement instrument can express per-case outcomes.
- Reporting of arm-level outcomes still requires P1.5a-style aggregate
  matrix; per-case signal does not by itself imply +3pp or any claim.

## Signature block (to be filled at approval)

- `signed_at_commit_sha`: ____
- `signed_by`: ____
- `signed_at_iso8601_utc`: ____
- `cost_latency_cap_token_budget`: ____
- `cost_latency_cap_wall_clock_s`: ____
- `regression_cap_error_class_delta_max_cases`: ____

---

This is **not** performance evidence, **not** a +3pp claim, **not**
Huawei acceptance evidence, and **not** scorer evidence. This is a
draft of an approval packet that, if signed, would authorize a bounded
rerun whose only output is per-case scorer-unit alignment for a
24-case target category.
