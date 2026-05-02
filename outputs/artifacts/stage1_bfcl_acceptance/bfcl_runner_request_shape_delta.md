# BFCL Runner Request Shape Delta

Status: no-provider shape-only artifact. No provider request, live telemetry rerun, BFCL smoke, scorer, full/default baseline, candidate activation, performance, +3pp, or Huawei path was run.

- suspected_gap: `bfcl_handler_missing_tool_choice_vs_telemetry_function_object`
- shape_deltas: `bfcl_handler_missing_tool_choice_vs_telemetry_function_object, bfcl_handler_missing_token_limit_vs_telemetry_max_output_tokens, bfcl_exact_id_payload_shape_not_exercised_by_synthetic_telemetry, bfcl_multiturn_history_shape_not_exercised_by_synthetic_telemetry, bfcl_runner_proxy_invocation_mode_differs_from_telemetry_client_factory`
- minimal_fix_recommended: `no_runtime_fix_yet_prepare_exact_bfcl_request_capture_or_patch_tool_choice_token_policy_after_review`

The artifact records labels and buckets only. It intentionally omits raw BFCL case content, prompts, gold/reference/expected material, scorer diffs, provider payloads, logs, traces, endpoint/key values, and candidate outputs.
