# Stage 1 BFCL Baseline Blocked Memo

Status: blocked. No BFCL measurement evidence exists at current head `1006dc95120817bc8b49a7350c1f2f9ab3075433`.

## Stop Condition

The exact 8-ID BFCL-shaped smoke remains blocked by repeated `Empty response from the model`. The run was stopped at observed progress `6/8` after both known protocol fixes were already in place:

- `max_tokens` / `max_output_tokens` path mismatch fixed.
- Responses `instructions` -> chat messages conversion loss fixed.

Reviewed 8-ID scope:

- `web_search_base_0`
- `memory_kv_0-customer-0`
- `multi_turn_base_0`
- `multi_turn_long_context_0`
- `multi_turn_miss_param_0`
- `multi_turn_miss_func_0`
- `irrelevance_0`
- `live_irrelevance_0-0-0`

## Gates Passed Before Smoke

- `check_bfcl_proxy_response_parser_debug_packet.py --compact --strict`
- `check_bfcl_proxy_runtime_adapter_shape_diff.py --compact --strict`
- `check_bfcl_stage1_smoke_run_id_manifest.py --compact --strict`
- `check_bfcl_stage1_smoke_scope_manifest.py --compact --strict`
- `check_bfcl_measurement_provider_protocol_debug_artifact.py --compact --strict`
- `check_bfcl_measurement_route_consistency.py --compact --strict`
- `check_bfcl_runner_interpreter.py --compact --strict`
- `check_artifact_boundary.py`

## Fixed Issues

- BFCL token field policy now uses path-specific `max_tokens` / `max_output_tokens` handling.
- Responses API `instructions` are preserved into chat messages before runtime/proxy execution.

## Unresolved Blocker

The exact BFCL-shaped runtime/proxy path still emits repeated `empty_model_response`. The offline synthetic parser path no longer reproduces the instruction-loss failure, so the remaining issue is not closed by the toy fixture.

## Cleaned State

- Temporary smoke root removed.
- Smoke output root removed.
- No smoke artifact committed.
- Worktree clean and branches synchronized as observed before this memo.

## Explicit No-Evidence Statement

- No full/default baseline ran.
- No validated BFCL measurement exists.
- No +3pp evidence exists.
- No candidate activation, candidate JSONL, or candidate pool exists.
- No scorer-feedback tuning occurred.
- No performance or Huawei claim is ready.
- No raw prompt, trace, provider payload, response body, gold/reference/expected, scorer diff, endpoint/key, or secret material was committed.

## Suspected Remaining Causes

- Real BFCL Responses request shape is not covered by the toy fixture.
- Runtime no-tool text-to-empty coercion may make nonempty text appear empty.
- Chat-to-Responses envelope conversion or BFCL SDK parser/decode behavior may still mismatch the BFCL-shaped path.

## Proposed Future Debug Gate

Prepare a no-provider BFCL client/proxy conformance harness before any retry. The harness should use a local fake upstream, synthetic toy request only, and the real BFCL/OpenAI client/parser path if importable. It must not call a provider, run BFCL smoke, run scorer, or read BFCL case content.

Future harness checks:

- Real client/proxy/fake-upstream returns a nonempty decoded function call.
- Responses `tool_choice` is normalized to chat-completions form.
- `max_output_tokens` is converted to chat `max_tokens` in the proxy call.
- Nonempty text-only no-tool output is classified as `no_tool_text`, not provider empty.
- True empty response is distinguishable from runtime-coerced empty.
- Responses output envelope includes required `function_call` fields.
