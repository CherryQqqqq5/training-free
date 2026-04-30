# Scored Failure Taxonomy Score Inventory

Inventory only. No scorer, provider, candidate run, or paired comparison was executed.

## Scope

- current provider route: `Chuangzhi/Novacode`
- current model: `gpt-5.2`
- performance_evidence: `false`
- candidate_pool_authorized: `false`
- scorer_authorization_for_performance: `false`
- huawei_acceptance_ready: `false`
- sota_3pp_claim_ready: `false`

## Counters

| counter | value |
| --- | ---: |
| score_file_count | 3 |
| candidate_score_file_count | 0 |
| baseline_score_file_count | 3 |
| route_model_matched_score_file_count | 0 |
| stale_or_mixed_score_reject_count | 3 |
| current_case_overlap_count | 22 |
| existing_clean_score_usable | false |
| baseline_only_scorer_needed | true |

## Decision

- existing_clean_score_usable: `false`
- baseline_only_scorer_needed: `true`
- reason: No existing score file passed current Chuangzhi/Novacode gpt-5.2 route/model and clean-field checks.

## Existing Score Files

| source | baseline/candidate | lines | overlap | route/model matched | rejected | reasons |
| --- | --- | ---: | ---: | --- | --- | --- |
| `184a55f6080ff9f7` | baseline | 8 | 7 | `false` | `true` | bfcl_runner_path_alias_or_model_path_not_authoritative_current_model; score_file_lacks_authoritative_gpt_5_2_model_match; score_file_contains_forbidden_fields:possible_answer; score_file_contains_non_approved_fields:inference_log,model_result_decoded,model_result_raw,possible_answer,prompt |
| `13aa71b50439f3c3` | baseline | 8 | 7 | `false` | `true` | bfcl_runner_path_alias_or_model_path_not_authoritative_current_model; score_file_lacks_authoritative_gpt_5_2_model_match; score_file_contains_forbidden_fields:possible_answer; score_file_contains_non_approved_fields:inference_log,model_result_decoded,model_result_raw,possible_answer,prompt |
| `da1c3916e3cc341e` | baseline | 9 | 8 | `false` | `true` | bfcl_runner_path_alias_or_model_path_not_authoritative_current_model; score_file_lacks_authoritative_gpt_5_2_model_match; score_file_contains_forbidden_fields:possible_answer; score_file_contains_non_approved_fields:inference_log,model_result_decoded,model_result_raw,possible_answer,prompt |

## Baseline-Only Scorer Request Needed

If the aggregate taxonomy audit proceeds, request separate baseline-only scorer authorization. Scope: current source case ids/categories, Chuangzhi/Novacode `gpt-5.2` metadata, raw outputs under `/tmp` only, tracked outputs limited to compact aggregate counters/hashes/route-model-case overlap metadata. Forbidden outputs remain gold text, expected values, candidate JSONL, dev/holdout manifests, per-case repair recommendations, and any performance/SOTA/Huawei claim.
