# Stage1 G7-revised — per_selected_id_score_adapter v2 design

Status: shipped on feature branch `feat/per-selected-id-score-adapter-v2`.
Replaces P1's matrix-based promotion logic with a direct read from
the sanitized per-case diagnostic emitted by G6b-2's live baseline arm run.

## Why a v2 was needed

P1's adapter (`abhe_v0_true_per_selected_id_score_adapter.json`) reported
`target_promoted_direct_count = 17/24` and
`score_output_contract_satisfied_for_target = false`.

Its promotion rule required "scorer_unit covers EXACTLY ONE selected
compact case". The input matrix had `scorer_unit_hash` mostly aggregated
to category level for the 24 multi_turn_miss_param cases, blocking
direct promotion for 7 of them.

G6b-2 (live baseline arm run, 2026-05-20) discovered the underlying
BFCL evaluator output ALREADY exposes per-case PASS/FAIL via:
  - row 0 of the score JSON: aggregate (correct=7, total=24)
  - rows 1-17: per-case invalid records (id, error_type_class, etc.)
  - implicit pass for the 7 IDs NOT in the invalid set

The "C1 scorer collapse" was thus a parsing artifact of the
per_selected_id_matrix builder's hash scheme, not a fundamental scorer
property. No per-case scorer invocation slicing is needed; a smarter
adapter that reads BFCL's batched score JSON is sufficient.

## What v2 does

1. Reads
   `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_baseline_arm_residual_smoke_per_case_diagnostic.json`
   (committed in G6b-2; sanitized; case_id + category + passed + error_type_class).
2. Filters to the 24 multi_turn_miss_param case records.
3. Emits ONE row per case with:
     - `arm = "baseline"` (only baseline available; other arms pending)
     - `case_id = "multi_turn_miss_param_<N>"` (BFCL public ID)
     - `per_selected_pass_available = true` (all 24 promoted)
     - `pass_bool` = the diagnostic's `passed` boolean
     - `promotion_source = "direct_from_bfcl_score_json_invalid_record_set_diff"`
     - `promotion_blocker = null`
     - `error_type_class` = BFCL's own classification (e.g.
       `multi_turn:instance_state_mismatch`)
4. Emits a strict-schema artifact + a strict checker that fails fast.

## Headline numbers (machine-verified)

| Metric | P1 (matrix-based) | G7-revised (direct) |
|---|---|---|
| `target_total_count` | 24 | 24 |
| `target_promoted_direct_count` | **17** | **24** |
| `score_output_contract_satisfied_for_target` | **false** | **true** |
| `target_pass_count` | (not exposed) | 7 |
| `target_fail_count` | (not exposed) | 17 |

The P1 artifact is preserved as evidence of the prior approach; G7-revised
does NOT modify it.

## What v2 does NOT do

- Does NOT call provider / BFCL / scorer
- Does NOT touch any existing artifact (purely additive)
- Does NOT cover conditional_frozen_v2 / runtime_slot_controller_v2 yet
  (their arm runs are pending; the v2 builder is arm-aware and will
   re-emit when their diagnostics land)
- Does NOT replace P1.5a category-arm-error-class matrix (that's G7b
  if/when we need an updated matrix using v2-promoted labels)
- Does NOT claim performance / SOTA / +3pp / Huawei readiness

## Pre-merge gate (all green)

- 10 core checkers: 9 exit 0 + 1 by-design fail-closed
  (`check_abhe_score_output_contract_satisfied` still exits 1 because
  the P1 ARTIFACT is unchanged; the v2 contract is satisfied by
  `check_abhe_v0_per_selected_id_score_adapter_v2_ready --strict` exit 0)
- 17 new tests in `tests/test_abhe_v0_per_selected_id_score_adapter_v2.py`
- Blast-radius guard extended to 15 files; 0 forbidden imports

## Boundary invariants (all preserved)

`performance_evidence=false`, `raw_material_absent=true`,
`raw_prompt_committed=false`, `raw_response_committed=false`,
`gold_expected_committed=false`, `argument_values_committed=false`,
`scorer_diff_committed=false`, `raw_provider_payload_committed=false`,
`raw_bfcl_result_tree_committed=false`, `prompt_literal_committed=false`,
`sota_3pp_claim_ready=false`, `huawei_acceptance_ready=false`,
`holdout_touched=false`, `full_suite_touched=false`,
`archive_updated=false`.

## Next steps (require user "go" for #1; the rest are passive)

1. Run conditional_frozen_v2 + runtime_slot_controller_v2 arms (~60 min,
   ~$10-20). For each, re-run the diagnostic extractor, then re-run
   the v2 adapter to add their rows. After all 3 arms have promoted
   labels, do arm-level evaluation per user instruction #3.
2. Consider deprecating the old per-case scorer slicer infrastructure
   (G6a manifest, G6b-1 executor) since G7-revised supersedes its goal.
   Keep them in git history as evidence of the search.
3. P1.5a category-arm-error-class matrix v2 can be built when all
   3 arms have v2 rows (then per-case-arm comparison is possible).
