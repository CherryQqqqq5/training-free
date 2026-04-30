# Stage-1 BFCL Active Evidence Index

This index is the current active-evidence pointer for Stage-1 BFCL. It is not a performance claim or Huawei acceptance claim.

## Active Provider

- provider: Chuangzhi/Novacode
- profile: novacode
- model: gpt-5.2
- expected env: NOVACODE_API_KEY
- base URL: https://apicz.boyuerichdata.com/v1
- OpenRouter: disabled / excluded

## Readiness

- performance_evidence: false
- scorer_authorization: false
- candidate_pool_ready: false
- sota_3pp_claim_ready: false
- huawei_acceptance_ready: false

## Current Blocker

`deterministic_argument_and_structural_paths_zero_yield_research_review_triggered`.
Provider and dataset are not the current blocker. Explicit literal, wrong-key alias, schema-local normalization, and refined structural raw-response attribution are all zero-yield under current offline diagnostics. No source expansion, scorer run, candidate promotion, performance claim, SOTA claim, or Huawei acceptance claim is authorized.

## Active Evidence Paths

- provider_green_preflight: `outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.json`
- provider_canonical_status: `outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json`
- bfcl_installed_dataset_export_gate: `outputs/artifacts/stage1_bfcl_acceptance/source_collection_authorization_batch1.json`
- bfcl_installed_dataset_export_gate_status: `{"dataset_export_signed": true, "dataset_gate_passed": true, "provider_green_signed": true}`
- batch1_full50_diagnostic: `outputs/artifacts/stage1_bfcl_acceptance/batch1_full50_extractor_yield_diagnostic.json`
- batch1_source_compact_artifacts: `outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_miss_func/baseline/artifacts/`
- batch2_pilot_diagnostic: `outputs/artifacts/stage1_bfcl_acceptance/batch2_source_collection_pilot_snapshot.json`
- batch2_source_compact_artifacts: `["outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_base/baseline/artifacts/", "outputs/artifacts/bfcl_ctspc_source_pool_v1/multi_turn_long_context/baseline/artifacts/"]`
- candidate_pool_status: `candidate_pool_not_ready`
- wrong_arg_key_alias_repair_diagnostic: `outputs/artifacts/stage1_bfcl_acceptance/wrong_arg_key_alias_repair_diagnostic.json`
- schema_local_non_live_repair_diagnostic: `outputs/artifacts/stage1_bfcl_acceptance/schema_local_non_live_repair_diagnostic.json`
- selected_call_structural_failure_attribution: `outputs/artifacts/stage1_bfcl_acceptance/selected_call_structural_failure_attribution.json`
- selected_call_structural_failure_attribution_raw_pilot: `outputs/artifacts/stage1_bfcl_acceptance/selected_call_structural_failure_attribution_raw_pilot.json`

## Uniform Counter Table

| category | result_jsonl_rows | parsed_emitted_calls | historical_call_count | selected_call_count | selected_calls_with_function_schema | selected_calls_with_required_args | selected_calls_with_missing_required | selected_calls_with_exactly_one_missing_required_arg | accepted_candidates | reject_reason_counts | selected_calls_with_schema_properties | selected_calls_with_empty_required |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multi_turn_miss_func | 50 | 557 | 407 | 150 | 70 | 65 | 0 | 0 | 0 | `{"ambiguous_literal": 44, "no_single_missing_required_arg": 6}` | 70 | 5 |
| multi_turn_base | 20 | 207 | 160 | 47 | 27 | 25 | 0 | 0 | 0 | `{"ambiguous_literal": 18, "no_single_missing_required_arg": 2}` | n/a | n/a |
| multi_turn_long_context | 20 | 191 | 139 | 52 | 32 | 30 | 0 | 0 | 0 | `{"ambiguous_literal": 18, "no_single_missing_required_arg": 2}` | n/a | n/a |

## Excluded / Superseded Evidence

- `outputs/artifacts/stage1_bfcl_acceptance/provider_unblock_current_failure.json`: historical provider failure before Chuangzhi/Novacode gpt-5.2 green; excluded from active Stage-1 claim
- `outputs/artifacts/stage1_bfcl_acceptance/provider_unblock_current_failure.md`: historical provider failure before Chuangzhi/Novacode gpt-5.2 green; excluded from active Stage-1 claim
- `outputs/artifacts/stage1_bfcl_acceptance/provider_unblock_request.md`: historical provider unblock request; excluded from active Stage-1 claim
- `outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_execution_status.json`: may describe earlier source status/defaults; active status is this index plus Batch1/Batch2 compact diagnostics
- `outputs/artifacts/bfcl_ctspc_source_pool_v1/source_collection_execution_status.md`: may describe earlier source status/defaults; active status is this index plus Batch1/Batch2 compact diagnostics
- `outputs/artifacts/bfcl_ctspc_subset30_v1/`: old CTSPC subset/candidate artifacts; not current Stage-1 active evidence
- `outputs/artifacts/bfcl_explicit_required_arg_literal_v1/*dev20*`: old dev20 manifests; current candidate pool is not ready and no dev/holdout split is authorized
- `outputs/artifacts/bfcl_explicit_required_arg_literal_v1/*candidate_rules.jsonl`: old candidate JSONL; current active candidate pool is not ready
- `outputs/artifacts/bfcl_explicit_required_arg_literal_v1/rejected_candidates.jsonl`: old candidate-family artifact; not active Stage-1 claim evidence
- `outputs/artifacts/phase2/`: memory/postcondition artifacts belong to Phase-2, not active Stage-1 BFCL +3pp evidence
- `any OpenRouter, old 401, or gpt-5.4 provider/source status references`: superseded by Chuangzhi/Novacode gpt-5.2 green route and excluded from active Stage-1 claim

## Pivot / Research Review

All checked deterministic argument and structural families are zero-yield and not scorer-authorized:

- `explicit_required_arg_literal_completion`: zero accepted; selected-call diagnostics show `selected_calls_with_missing_required=0` and `selected_calls_with_exactly_one_missing_required_arg=0` across active Batch1/Batch2 diagnostics.
- `wrong_arg_key_alias_repair`: offline diagnostic run; `alias_repair_eligible_count=0`.
- `deterministic_schema_local_non_live_repair`: offline diagnostic run; `schema_local_repair_eligible_count=0`.
- `structural_raw_response_attribution_malformed_final_before_tool`: refined raw-response attribution approved as active negative evidence; `parser_refined=true`, `raw_candidate_tool_call_count=25`, `raw_schema_matched_tool_call_count=14`, `eligible_structural_count=0`.

Structural expansion to 20/category is unauthorized. Scorer, candidate pool promotion, +3pp/SOTA claim, and Huawei acceptance claim remain unauthorized.

Pending research-review item only: `scored_failure_attribution_outcome_surface_audit`. It is not authorized yet, not implemented, not candidate extraction, not a scorer/gold/outcome audit started here, and not a performance claim.

## Delivery Risk

Current work is on `stage1-bfcl-performance-sprint`; main merge decision is pending. This is delivery-risk tracking, not an acceptance claim. Index provenance: source_base_head `6e3a1e63`, index_source_head `15f611d7`.
