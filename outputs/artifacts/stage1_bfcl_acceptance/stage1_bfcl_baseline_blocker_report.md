# Stage 1 BFCL Baseline Blocker Report

Status: Stage 1 remains blocked. No BFCL measurement evidence exists.

- current_head_observed: `25a908e80c9162a699cbbf87b7f67d2826e5c871`
- runtime_blocker_base_commit: `1006dc95120817bc8b49a7350c1f2f9ab3075433`
- exact 8-ID BFCL-shaped smoke materialized: `true`
- stop condition: repeated `Empty response from the model`
- stopped progress: `6/8`
- observed after max token fix: `true`
- observed after Responses instructions preservation fix: `true`

## Gates Passed Before Smoke

- `check_bfcl_proxy_response_parser_debug_packet.py --compact --strict`
- `check_bfcl_proxy_runtime_adapter_shape_diff.py --compact --strict`
- `check_bfcl_stage1_smoke_run_id_manifest.py --compact --strict`
- `check_bfcl_stage1_smoke_scope_manifest.py --compact --strict`
- `check_bfcl_measurement_provider_protocol_debug_artifact.py --compact --strict`
- `check_bfcl_measurement_route_consistency.py --compact --strict`
- `check_bfcl_runner_interpreter.py --compact --strict`
- `check_artifact_boundary.py`

## Reviewed Run IDs

- `web_search_base_0`
- `memory_kv_0-customer-0`
- `multi_turn_base_0`
- `multi_turn_long_context_0`
- `multi_turn_miss_param_0`
- `multi_turn_miss_func_0`
- `irrelevance_0`
- `live_irrelevance_0-0-0`

## Known Fixed Issues

- `max_tokens` / `max_output_tokens` path mismatch.
- Responses `instructions` -> chat messages conversion loss.

## Current Blocker

The exact BFCL-shaped runtime/proxy path still repeatedly emits `empty_model_response` and cannot produce validated Stage 1 measurement evidence. The smoke tmp root and output root were removed, and no smoke artifact was committed.

## Explicit Non-Evidence Statement

No full/default baseline, candidate activation, candidate JSONL/pool, scorer-feedback tuning, performance evidence, +3pp claim, Huawei claim, raw payload, raw case content, or secret material was committed.

Provenance note: `prior_blocked_memo_commit=97bd2c49bc31c6a15123c53ab99a54436ec92e87`; the runtime blocker base remains recorded separately.
