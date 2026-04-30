# Raw Response Capture Source Collection Authorization

This is a compact authorization boundary only. It does not start provider calls or source collection.

- source_collection_rerun_for_raw_response_only: `true`
- purpose: capture `raw_response` / `raw_response_text` for structural attribution only
- categories: `multi_turn_miss_func`, `multi_turn_base`, `multi_turn_long_context`
- pilot size: 10 per category, total 30
- expansion gate: `raw_response_present_count/result_jsonl_rows >= 0.95` and `bad_jsonl_rows=0`
- provider route: Chuangzhi/Novacode, profile `novacode`, model `gpt-5.2`, env `NOVACODE_API_KEY`
- OpenRouter: disabled / forbidden
- scorer_authorization: `false`
- candidate_pool_ready: `false`
- performance_evidence: `false`
- huawei_acceptance_ready: `false`
- sota_3pp_claim_ready: `false`
- raw storage: `/tmp/bfcl_source_collection_raw_response_capture` only
- tracked outputs: compact counters, manifest, hashes only

## Forbidden Fields

`gold`, `expected`, `answer`, `ground_truth`, `oracle`, `score`, `candidate`, `repair`, `reference`, `possible_answer`

## Required Capture Fields

`case_id`, `category`, `provider_route`, `model_id`, `dataset_record_hash`, `tool_schema_hash`, `prompt_hash`, `raw_response/raw_response_text`, `baseline_parsed_result`, `parse_status`, `parse_error_type`, `selected_turn_index`, `selected_call_count`, `schema_match_status`

## Run Boundary

Do not start provider/source collection until an explicit run task is issued.
