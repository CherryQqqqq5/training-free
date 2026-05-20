# G6b-2 Baseline arm residual smoke — honest findings (2026-05-20)

Live execution of `run_abhe_v0_runtime_slot_controller_residual_dev_smoke.py --arm baseline`
on the existing approved 48-case `distinct_rerun` slice (which includes the
24 multi_turn_miss_param target cases the P1.5b packet authorized).

## Run metadata

- **Started**: 2026-05-20T03:13:30Z
- **Ended**:   2026-05-20T03:51:59Z
- **Wall-clock**: ~38 minutes
- **Cost**: ≈ $5-10 (gpt-4.1 via TooCallingFunction endpoint; token capture was None in BFCL output, so exact dollars not computed)
- **Provider 504s**: **0**
- **Provider 5xx errors**: **0**
- **Exit code**: 0 (clean completion)
- **Arms executed**: 1 of 3 (baseline only). conditional_frozen_v2 + runtime_slot_controller_v2 NOT yet run.

## Result aggregate (per BFCL evaluator output)

| Category | n | pass | acc | invalid_records_in_score_json |
|---|---|---|---|---|
| multi_turn_miss_param | **24** | **7** | **29.2%** | 17 |
| multi_turn_miss_func | 6 | 1 | 16.7% | 5 |
| multi_turn_base | 6 | 4 | 66.7% | 2 |
| multi_turn_long_context | 4 | 2 | 50.0% | 2 |
| irrelevance | 4 | 0 | 0.0% | 4 |
| live_irrelevance | 4 | 0 | 0.0% | 4 |
| **TOTAL** | **48** | **14** | **29.2%** | 34 |

## Bottleneck assessment — **none of the predicted bottlenecks reproduced**

### 1. Provider 504 bottleneck (C3): **NOT observed**
The prior distinct_rerun attempt reportedly got 504s on multi_turn_miss_param.
This run: **0 504s, 0 5xx errors, provider stable for the full 38-min run**.
Conclusion: C3 was either transient or the provider has stabilized. Backoff
wiring (P3-wire / G6b-2's hard caps) is therefore not on the critical path
*for this slice on this day*.

### 2. Scorer collapse bottleneck (C1): **data was always there**
The original C1 claim was "24 cases collapsed into 1 scorer_unit, per-case
pass labels unavailable". The actual BFCL score JSON has:
  - **Row 0**: aggregate (`correct_count=7, total_count=24`)
  - **Rows 1-17**: 17 invalid-case records with full `id`, `valid: false`,
    `error.error_message`, `error.error_type`, `inference_log`, etc.
  - **Implied row 18-24**: 7 passing IDs (those NOT in the invalid set)

So per-case PASS/FAIL labels are **directly available** from the existing
batched score JSON. The "P1.5b per-case scorer slicer" infrastructure
(G6a manifest, G6b executor scaffold) **doesn't need to invoke scorer
24 separate times** — it just needs a smarter adapter that:
  1. Lists all 24 selected IDs from result file
  2. Marks `passed=true` for IDs NOT in score json's invalid records
  3. Marks `passed=false` + records `error_type_class` for IDs in invalid records

The original `abhe_v0_runtime_slot_controller_per_selected_id_matrix.json`
got `unique scorer_unit_hash = 1` for miss_param because it used a
category-level hash, not because the data was truly aggregated. **The
runner's own compact output already reports `unique_scorer_unit_count = 24`
for multi_turn_miss_param in this run.**

### 3. Real bottleneck = **model capability on multi-turn state tracking**

Sanitized error_type_class distribution across all 48 failures (34 failures):

| count | error_type_class |
|---|---|
| **18** | `multi_turn:instance_state_mismatch` |
|  8 | `irrelevance_error:decoder_success` |
|  4 | `multi_turn:empty_turn_model_response` |
|  2 | `multi_turn:execution_response_mismatch` |
|  2 | `multi_turn:force_terminated` |
| 14 | `passed` |

The model (gpt-4.1 via ToolCallingFunction) **fails the BFCL state-based
evaluation** for multi-turn cases because its tool calls don't drive the
simulated backend (VehicleControlAPI, TwitterAPI, MessageAPI, TradingBot,
GorillaFileSystem) into the ground-truth final state. This matches the
BFCL-v3 blog's design intent: state-based eval is harder than
trajectory-matching, and the model has to actually solve the task.

For irrelevance: model decodes an AST when it should abstain — a
**relevance-detection** failure unrelated to multi-turn state.

## Per-case detail (TARGET = multi_turn_miss_param)

| case_id | pass | error_type_class | turns | latency_s |
|---|---|---|---|---|
| 77 | PASS | passed | 4 | 125.5 |
| 88 | PASS | passed | 4 | 13.5 |
| 94 | PASS | passed | 4 | 37.8 |
| 97 | PASS | passed | 7 | 59.5 |
| 100 | PASS | passed | 3 | 22.7 |
| 103 | PASS | passed | 6 | 31.6 |
| 105 | PASS | passed | 3 | 21.1 |
| 76 | FAIL | instance_state_mismatch | 3 | 14.3 |
| 78 | FAIL | instance_state_mismatch | 3 | 83.9 |
| 79 | FAIL | instance_state_mismatch | 4 | 40.7 |
| 86 | FAIL | instance_state_mismatch | 4 | 35.0 |
| 87 | FAIL | instance_state_mismatch | 5 | 19.0 |
| 89 | FAIL | instance_state_mismatch | 5 | 15.9 |
| 90 | FAIL | instance_state_mismatch | 5 | 29.7 |
| 91 | FAIL | instance_state_mismatch | 3 | 20.3 |
| 92 | FAIL | instance_state_mismatch | 6 | 18.2 |
| 93 | FAIL | instance_state_mismatch | 4 | 13.2 |
| 96 | FAIL | instance_state_mismatch | 3 | 23.8 |
| 98 | FAIL | instance_state_mismatch | 4 | 47.8 |
| 99 | FAIL | instance_state_mismatch | 5 | 28.8 |
| 102 | FAIL | instance_state_mismatch | 6 | 16.4 |
| 101 | FAIL | empty_turn_model_response | 4 | 6.6 |
| 104 | FAIL | empty_turn_model_response | 3 | 19.8 |
| 95 | FAIL | empty_turn_model_response | 6 | 40.4 |

15/17 multi_turn_miss_param failures are state-mismatch; 3/17 are empty-response.

## Boundary discipline — all preserved

| Field | Value |
|---|---|
| performance_evidence | false |
| raw_material_absent | true |
| raw_prompt_committed | false |
| raw_response_committed | false |
| raw_provider_payload_committed | false |
| raw_bfcl_result_tree_committed | false |
| gold_expected_committed | false |
| argument_values_committed | false |
| scorer_diff_committed | false |
| prompt_literal_committed | false |
| sota_3pp_claim_ready | false |
| huawei_acceptance_ready | false |
| holdout_touched | false |
| full_suite_touched | false |
| archive_updated | false |

The committed diagnostic JSON contains only: case_id (public BFCL ID),
category (public name), passed (bool), error_type_class (BFCL's own
sanitized class label), turn_count (number), latency_s (number).
**No prompts, no gold, no expected, no argument values, no raw responses.**

The /tmp run_root retains everything (results, scores, traces) for
**local inspection only** — never committed to git.

## Implications for P1.5b plan

Original 5-step plan revisited in light of these findings:

1. **#1 P1.5b signed + caps** ✅ already done (G5).
2. **#2 per-case scorer slicer rerun to make 24 cases → 24 unique scorer_units**:
   The user-stated goal was "24 unique scorer_units for the target". The
   actual BFCL evaluator **already produces per-case structured data**
   (17 invalid records + 7 implied passing). The slicer per-case invocation
   pattern (running `bfcl evaluate` 24 separate times) is technically
   unnecessary; what's needed is a better adapter. Recommend:
   - **G7-revised**: write `build_abhe_v0_per_selected_id_score_adapter_v2.py`
     that reads the on-disk batched score JSON and computes per-case
     pass labels from the invalid+result-id-set difference.
   - This replaces the original P1's adapter (`v0_true_per_selected_id_score_adapter`)
     and would set `target_promoted_direct_count = 24/24` directly.
3. **#3 arm-level eval only after contract satisfied**: still applies.
   To compare arms, need to run conditional_frozen_v2 and
   runtime_slot_controller_v2 (each ~30 min, ~$5-10 on this slice).
4. **#4 v3 wired bounded test**: orthogonal to the slicer question.
   Can proceed independently after #2 is solved structurally.
5. **#5 backoff in separate PR**: 0 504s observed; backoff is no longer
   on the critical path for this slice. Still worth shipping as defensive.

## Recommendation

Skip the "per-case scorer slicer invocation" entirely. Instead:

1. Build the v2 score adapter (G7-revised) — pure offline; no provider
   call needed.
2. Verify on this baseline run that 24/24 pass labels are recoverable.
3. Run conditional_frozen_v2 (~30 min) and runtime_slot_controller_v2
   (~30 min) for arm comparison.
4. Then re-evaluate per user instruction #3.

Total remaining cost: ~$10-20 + ~60 min for the two missing arms.
No new provider call needed for the slicer fix (it's pure parsing).
