# BFCL Stage 1 Smoke Scope Manifest

Status: `pending`. This is a scope preparation artifact only. It does not authorize provider calls, BFCL smoke execution, BFCL full/default evaluation, scorer execution, candidate activation, candidate JSONL, candidate pools, performance evidence, +3pp claims, SOTA claims, or Huawei readiness.

## Scope Decision

The existing Stage 1 BFCL runner can filter by BFCL category and can technically use BFCL `--run-ids` via `GRC_BFCL_USE_RUN_IDS=1` with `<run_root>/bfcl/test_case_ids_to_generate.json`. However, the reviewed Stage 1 smoke scope does not yet include a signed run-id manifest or reviewer-confirmed mapping from the eight Stage 1 source categories to exact BFCL cases. Therefore smoke execution is stopped before any provider/BFCL call.

## Required Future Scope

- Maximum total cases: `8`
- Preferred shape: exactly one case per approved Stage 1 source category
- Source categories: `agentic_web_search`, `agentic_memory`, `multi_turn_base`, `multi_turn_long_context`, `multi_turn_miss_param`, `multi_turn_miss_func`, `hallucination`, `irrelevance`
- BFCL category mapping status: `pending_reviewer_confirmation`
- Case selection status: `pending_reviewed_run_ids_materialization`
- Selected case IDs committed here: `false`
- Raw case or nonce mapping committed here: `false`

## Fixed Route And Boundaries

- Route: `novacode` / `gpt-4.1`
- gpt-4o fallback: `false`
- OpenRouter: `false`
- endpoint/key: env-only, values not committed
- candidate specs inert: `true`
- candidate activation/JSONL/pool: `false`
- scorer/performance/+3pp/Huawei: `false`

This artifact is not full/default baseline evidence and not performance evidence.
