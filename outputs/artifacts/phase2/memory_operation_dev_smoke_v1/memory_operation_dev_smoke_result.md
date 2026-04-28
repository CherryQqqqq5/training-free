# M2 Memory Operation Dev Smoke Result

## Verdict

This smoke run produced no retain rule and no BFCL improvement claim. The prereq snapshot setup was available, but both baseline and candidate scored 0 on the 6 memory targets because every target ended without a final assistant message after the memory tool call.

## Key Metrics

- `target_case_count`: `6`
- `generation_case_count`: `26`
- `prereq_case_count`: `20`
- `baseline_accuracy`: `0.0`
- `candidate_accuracy`: `0.0`
- `absolute_pp_delta`: `0.0`
- `case_fixed_count`: `0`
- `case_regressed_count`: `0`
- `net_case_gain`: `0`
- `candidate_changed_retrieval_keys_count`: `2`
- `target_scorer_valid_count_baseline`: `0`
- `target_scorer_valid_count_candidate`: `0`

## Failure Mode

- `dominant_failure_mode`: `agentic:no_last_message`
- Baseline and candidate both called memory tools on all target cases.
- Candidate changed 2 KV retrieval keys, but this did not become target success because the final textual answer was missing.
- Interpretation: memory retrieval selection alone is insufficient; the next theoretical question is whether a second-pass memory observation to final-answer bridge is a principled retain family.

## Guardrails

- `retain_rule_created`: `false`
- `bfcl_plus_3pp_claim`: `false`
- `dev_scorer_authorized_next`: `false`
- `holdout_authorized`: `false`
- `hundred_case_authorized`: `false`
- `full_bfcl_authorized`: `false`

## Next Route

`investigate_second_pass_final_answer_policy_or_memory_tool_result_to_answer_bridge_before_any_new_scorer`

## Changed Retrieval Keys

- `memory_kv_1-customer-1`: baseline `{'tool': 'core_memory_retrieve', 'args': '{"key":"customer_profile"}'}` -> candidate `{'tool': 'core_memory_retrieve', 'args': '{"key":"customer_age"}'}`
- `memory_kv_2-customer-2`: baseline `{'tool': 'core_memory_retrieve', 'args': '{"key":"customer_profile"}'}` -> candidate `{'tool': 'core_memory_retrieve', 'args': '{"key":"customer_location"}'}`
