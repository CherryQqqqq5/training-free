# BFCL Tool Choice Normalization Patch Gate Packet

Status: prepared and fail-closed. This packet does not authorize a behavior patch or any execution.

## Scope Requested For Future Review

- Patch name: `bfcl_measurement_responses_to_chat_tool_choice_normalization`
- Patch kind: `proxy_normalization`
- Target scope: `bfcl_measurement_generate_path_only`
- Condition: `tools_present_and_tool_choice_missing_or_none`
- Normalized tool choice: `required`
- Route: `novacode/gpt-4.1`

## Explicit Non-Authorization

The current packet keeps patching, provider requests, live telemetry, BFCL generate/smoke/evaluate, scorer, full baseline, candidate paths, and performance claims unauthorized. It is a review gate only.

## Boundary

Future work, if separately approved, must remain measurement/generate path only and must not broaden into candidate, scorer, baseline, performance, or general runtime behavior unless a separate review expands scope.
