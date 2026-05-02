# BFCL Stage 1 Smoke Run-ID Manifest

Status: `prepared`, not executable. This artifact prepares an exact BFCL run-id scope for reviewer approval. It does not authorize provider calls, BFCL smoke execution, BFCL full/default evaluation, scorer execution, candidate activation, candidate JSONL, candidate pools, performance evidence, +3pp claims, SOTA claims, or Huawei readiness.

## Fixed Route

- Route: `novacode` / `gpt-4.1`
- Historical inactive route: `gpt-5.2`
- gpt-4o fallback: `false`
- OpenRouter: `false`
- endpoint/key: env-only, values not committed

## Exact Prepared Scope

Total cases: `8`, one run ID per BFCL category listed below.

| Source category | BFCL category | Run ID | Selection rule |
| --- | --- | --- | --- |
| `agentic_web_search` | `web_search_base` | `web_search_base_0` | `first_id_in_installed_bfcl_category_metadata` |
| `agentic_memory` | `memory_kv` | `memory_kv_0-customer-0` | `first_non_prereq_id_in_existing_source_pool` |
| `multi_turn_base` | `multi_turn_base` | `multi_turn_base_0` | `first_id_in_existing_source_pool` |
| `multi_turn_long_context` | `multi_turn_long_context` | `multi_turn_long_context_0` | `first_id_in_existing_source_pool` |
| `multi_turn_miss_param` | `multi_turn_miss_param` | `multi_turn_miss_param_0` | `first_id_in_existing_source_pool` |
| `multi_turn_miss_func` | `multi_turn_miss_func` | `multi_turn_miss_func_0` | `first_id_in_existing_source_pool` |
| `hallucination` | `irrelevance` | `irrelevance_0` | `deterministic_abstention_proxy_first_id` |
| `irrelevance` | `live_irrelevance` | `live_irrelevance_0-0-0` | `deterministic_distinct_irrelevance_proxy_first_id` |

BFCL has no dedicated `hallucination` category in the installed v4 category set. The abstention-related source categories therefore use deterministic proxy categories and remain pending reviewer approval before any execution.

## Execution Boundary

If separately approved later, the runner must materialize the exact `run_ids_by_category` payload to `<run_root>/bfcl/test_case_ids_to_generate.json`, set `GRC_BFCL_USE_RUN_IDS=1`, and keep the category list fixed to the eight BFCL categories above. This artifact itself does not run or authorize smoke.

Raw prompts, traces, provider payloads or responses, gold/reference/expected material, scorer diffs, endpoint/key values, source nonce mappings, candidate outputs, and performance claims are not present and not authorized.
