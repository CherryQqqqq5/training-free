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

`deterministic_argument_structural_and_tool_name_paths_zero_yield`.
Provider and dataset are not the current blocker. Explicit literal, wrong-key alias, schema-local, refined structural raw-response, and raw schema-not-matched tool-name/schema normalization paths are all zero-yield under current gates. `next_action=negative_evidence_report_or_scope_change_review`. No source expansion, scorer run, candidate promotion, performance claim, SOTA claim, or Huawei acceptance claim is authorized.

## Active Evidence Paths

- provider_green_preflight_json: `outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.json`
- provider_green_preflight_md: `outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.md`
- provider_canonical_status_json: `outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json`
- provider note: provider green is technical preflight only and does not authorize scorer, candidate, paired-comparison, SOTA, or Huawei claims.
- bfcl_installed_dataset_export_gate: `outputs/artifacts/stage1_bfcl_acceptance/source_collection_authorization_batch1.json`
- batch1_full50_diagnostic: `outputs/artifacts/stage1_bfcl_acceptance/batch1_full50_extractor_yield_diagnostic.json`
- batch2_pilot_diagnostic: `outputs/artifacts/stage1_bfcl_acceptance/batch2_source_collection_pilot_snapshot.json`
- wrong_arg_key_alias_repair_diagnostic: `outputs/artifacts/stage1_bfcl_acceptance/wrong_arg_key_alias_repair_diagnostic.json`
- schema_local_non_live_repair_diagnostic: `outputs/artifacts/stage1_bfcl_acceptance/schema_local_non_live_repair_diagnostic.json`
- selected_call_structural_failure_attribution_raw_pilot: `outputs/artifacts/stage1_bfcl_acceptance/selected_call_structural_failure_attribution_raw_pilot.json`
- baseline_only_scored_failure_taxonomy_audit_json: `outputs/artifacts/stage1_bfcl_acceptance/baseline_only_scored_failure_taxonomy_audit.json`
- baseline_only_scored_failure_taxonomy_audit_md: `outputs/artifacts/stage1_bfcl_acceptance/baseline_only_scored_failure_taxonomy_audit.md`
- raw_payload_schema_not_matched_subtyping_audit_json: `outputs/artifacts/stage1_bfcl_acceptance/raw_payload_schema_not_matched_subtyping_audit.json`
- raw_payload_schema_not_matched_subtyping_audit_md: `outputs/artifacts/stage1_bfcl_acceptance/raw_payload_schema_not_matched_subtyping_audit.md`
- schema_retrieval_rerank_feasibility_diagnostic_json: `outputs/artifacts/stage1_bfcl_acceptance/schema_retrieval_rerank_feasibility_diagnostic.json`
- schema_retrieval_rerank_feasibility_diagnostic_md: `outputs/artifacts/stage1_bfcl_acceptance/schema_retrieval_rerank_feasibility_diagnostic.md`
- candidate_pool_status: `candidate_pool_not_ready`
- negative_evidence_report_md: `docs/stage1_bfcl_negative_evidence_report.md`

## Uniform Counter Table

| category | result_jsonl_rows | parsed_emitted_calls | historical_call_count | selected_call_count | selected_calls_with_function_schema | selected_calls_with_required_args | selected_calls_with_missing_required | selected_calls_with_exactly_one_missing_required_arg | accepted_candidates | reject_reason_counts | selected_calls_with_schema_properties | selected_calls_with_empty_required |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| multi_turn_miss_func | 50 | 557 | 407 | 150 | 70 | 65 | 0 | 0 | 0 | `{"ambiguous_literal": 44, "no_single_missing_required_arg": 6}` | 70 | 5 |
| multi_turn_base | 20 | 207 | 160 | 47 | 27 | 25 | 0 | 0 | 0 | `{"ambiguous_literal": 18, "no_single_missing_required_arg": 2}` | n/a | n/a |
| multi_turn_long_context | 20 | 191 | 139 | 52 | 32 | 30 | 0 | 0 | 0 | `{"ambiguous_literal": 18, "no_single_missing_required_arg": 2}` | n/a | n/a |

## Excluded / Superseded Evidence

- `outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.md`: superseded markdown contains old 401/OpenRouter/source_collection_rerun_ready=false wording; active provider evidence is provider_green_preflight.{json,md} plus current_provider_preflight_status.json only
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

All checked deterministic argument, structural, scored-taxonomy, and tool-name/schema paths are zero-yield or research-review only under current gates:

- `explicit_required_arg_literal_completion`: zero accepted; selected-call diagnostics show `selected_calls_with_missing_required=0` and `selected_calls_with_exactly_one_missing_required_arg=0` across active Batch1/Batch2 diagnostics.
- `wrong_arg_key_alias_repair`: offline diagnostic run; `alias_repair_eligible_count=0`.
- `deterministic_schema_local_non_live_repair`: offline diagnostic run; `schema_local_repair_eligible_count=0`.
- `structural_raw_response_attribution_malformed_final_before_tool`: refined raw-response attribution; `parser_refined=true`, `raw_candidate_tool_call_count=25`, `raw_schema_matched_tool_call_count=14`, `eligible_structural_count=0`.
- `baseline_only_scored_failure_taxonomy_audit`: completed as aggregate taxonomy only, not performance evidence. `scored_case_count=30`, `baseline_failure_count=22`, and taxonomy buckets are denominated by 22 failure detail rows, not by an overlap gap.
- `raw_payload_schema_not_matched_tool_name_schema_normalization`: raw schema-not-matched bucket 10/10 has no schema-name candidate and `deterministic_source_schema_only_possible_count=0`; deterministic tool-name/schema normalization family is not authorized.
- `schema_retrieval_rerank_feasibility`: zero-yield; `single_schema_high_margin_count=0`; recommendation `stop_no_yield_research_review`.

Latest conclusion: `deterministic_argument_structural_and_tool_name_paths_zero_yield=true`; `next_action=negative_evidence_report_or_scope_change_review`; `candidate_pool_ready=false`; `scorer_authorized=false`; `performance_evidence=false`; `sota_3pp_claim_ready=false`; `huawei_acceptance_ready=false`.

## Provenance Table

| artifact_path | evidence_role | source_code_head | artifact_commit | route/model | active/superseded |
| --- | --- | --- | --- | --- | --- |
| `outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.json` | technical provider preflight green only | `d39a954d` | `d39a954d` | Chuangzhi/Novacode gpt-5.2 | active |
| `outputs/artifacts/stage1_bfcl_acceptance/provider_green_preflight.md` | technical provider preflight green only | `d39a954d` | `d39a954d` | Chuangzhi/Novacode gpt-5.2 | active |
| `outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.json` | canonical provider preflight status JSON | `d39a954d` | `d39a954d` | Chuangzhi/Novacode gpt-5.2 | active |
| `outputs/artifacts/bfcl_ctspc_source_pool_v1/current_provider_preflight_status.md` | old provider markdown with 401/OpenRouter wording | `unknown_historical` | `unknown_historical` | old failure wording | superseded |
| `outputs/artifacts/stage1_bfcl_acceptance/batch2_source_collection_pilot_snapshot.json` | Batch2 source collection diagnostic only | `fa4156d0` | `6e3a1e63` | Chuangzhi/Novacode gpt-5.2; BFCL path aliases non-authoritative | active |
| `outputs/artifacts/stage1_bfcl_acceptance/baseline_only_scored_failure_taxonomy_audit.json` | aggregate scored failure taxonomy; not performance evidence | `f1fa5507/d48e6211` | `d48e6211` | Chuangzhi/Novacode gpt-5.2 source metadata | active |
| `outputs/artifacts/stage1_bfcl_acceptance/raw_payload_schema_not_matched_subtyping_audit.json` | raw schema-not-matched subtyping; zero-yield | `d1047b14` | `d1047b14` | Chuangzhi/Novacode gpt-5.2 source metadata | active |
| `outputs/artifacts/stage1_bfcl_acceptance/schema_retrieval_rerank_feasibility_diagnostic.json` | schema retrieval rerank feasibility; zero-yield | `a19f74c4` | `a19f74c4` | offline existing raw pilot only; no provider/scorer | active |

## Delivery Risk

- latest_branch_head_observed: `f8dcaae5`

Current work is on `stage1-bfcl-performance-sprint`; main merge decision is pending. This is delivery-risk tracking, not an acceptance claim. Index provenance: latest_branch_head_observed `f8dcaae5`; current_branch_head_at_review `f8dcaae5`; index_artifact_commit `f8dcaae5`; previous_latest_branch_head_observed `61611b98`; previous_current_branch_head_at_review `61611b98`; previous_index_artifact_commit `61611b98`; hygiene_patch_commit `27e36c25`; latest_hygiene_source_head `b94855e0`; source_base_head `6e3a1e63`; Batch2 source_collection_code_head `fa4156d0`; baseline taxonomy code head `d48e6211`; raw schema subtyping code head `d1047b14`; schema_retrieval_rerank_code_head `a19f74c4`; schema_retrieval_rerank_artifact_commit `a19f74c4`.

Provider artifact commits such as `d39a954d` are original evidence creation commits only, not the current branch checkpoint.

Provenance note: single ambiguous `head` field is intentionally not used; current index artifact commit is recorded separately from previous index values and earlier diagnostic/source heads.

Negative evidence report: `docs/stage1_bfcl_negative_evidence_report.md`.
