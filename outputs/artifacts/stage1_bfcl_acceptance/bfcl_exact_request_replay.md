# BFCL Exact Request Replay

Status: no-provider exact request replay with fake upstream. No provider request, live telemetry, BFCL smoke, scorer, full/default baseline, candidate activation, performance, +3pp, SOTA, or Huawei path was run.

- signed_run_ids: `web_search_base_0, multi_turn_base_0`
- fake_upstream_variants: `tool_call, text_only, true_empty, malformed_nonempty`
- required_string_multi_tool_survives_local_conversion_runtime_decode: `True`
- suspected_replay_failure_stage: `required_string_multi_tool_survives_local_conversion_runtime_decode`
- minimal_tool_choice_patch_recommended_next: `False`

The artifact is shape-only and omits raw prompt/content text, tool arguments, raw case material, gold/reference/expected, scorer diffs, provider payloads, headers, logs, traces, endpoint/key values, and candidate output.
