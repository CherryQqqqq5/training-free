# Scored Failure Taxonomy Audit Approval

This packet materializes approval for a strict aggregate-only scored failure taxonomy audit. It does not execute the audit and does not authorize scorer use for performance evidence.

## Scope Flags

- audit_only: `true`
- uses_scorer_or_gold: `true` for aggregate taxonomy only
- candidate_extraction_authorized: `false`
- candidate_pool_authorized: `false`
- scorer_authorization_for_performance: `false`
- performance_evidence: `false`
- sota_3pp_claim_ready: `false`
- huawei_acceptance_ready: `false`
- provider_run_authorized: `false`
- candidate_run_authorized: `false`
- paired_comparison_authorized: `false`
- gold_text_emitted: `false`
- expected_values_emitted: `false`
- per_case_repair_recommendations_emitted: `false`
- no_leakage_to_candidate_pool: `true`

## Allowed Fields

- `case_id`
- `category`
- `run_ids`
- `pass_fail`
- `failure_bucket`
- `tool_call_count_bucket`
- `argument_mismatch_bucket`
- `aggregate_percentages`
- `sample_hashes`
- `source_hashes`
- `scorer_version`
- `BFCL_version`
- `provider_metadata`
- `model_metadata`

## Forbidden Uses

- gold/expected literal extraction
- candidate JSONL
- dev/holdout manifest
- case selection for pool
- scorer-outcome-based eligibility
- performance evidence
- SOTA/+3pp claim
- expected/gold content emission
- per-case repair recommendations
- prompt/provider/model tuning

## Taxonomy Counters

- `audited_case_count`
- `scored_case_count`
- `score_file_count`
- `score_route_matched_count`
- `score_model_matched_count`
- `source_score_case_overlap_count`
- `missing_score_count`
- `stale_or_mixed_score_reject_count`
- `baseline_success_count`
- `baseline_failure_count`
- `baseline_success_rate`
- `baseline_failure_rate`
- `failure_with_no_tool_like_payload`
- `failure_with_raw_payload_schema_not_matched`
- `failure_with_selected_schema_not_matched`
- `failure_with_schema_valid_selected_calls`
- `failure_with_wrong_tool_or_order`
- `failure_with_argument_name_mismatch`
- `failure_with_argument_value_mismatch`
- `failure_with_execution_or_state_mismatch`
- `failure_with_extra_or_missing_call_count`
- `unattributed_failure_count`

## Next Execution Preference

First inspect and use existing clean score outputs only if route, model, and case overlap checks pass. If clean scores are absent, request separate baseline-only scorer authorization. No new scorer, provider, candidate run, or paired comparison is authorized by this packet.

## Boundary

The audit is aggregate-only. It may not emit gold/expected content, candidate JSONL, dev/holdout manifests, per-case repair recommendations, scorer-outcome-based eligibility, or performance/SOTA/Huawei acceptance evidence.
