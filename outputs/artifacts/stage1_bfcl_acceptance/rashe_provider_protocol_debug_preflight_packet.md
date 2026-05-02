# RASHE Provider Protocol Debug Preflight Packet

Status: approved execution packet for one synthetic protocol debug only. This packet does not authorize Phase B/source diagnostics.

## Scope

- signed_model: `gpt-4.1`
- provider_profile: Chuangzhi/Novacode
- approval_status: `approved`
- authorized: `true`
- execution_authorized: `true`
- provider_request_authorized: `true`
- execution_scope: `single_synthetic_protocol_debug_only`
- endpoint env vars: `CHUANGZHI_NOVACODE_ENDPOINT`, `NOVACODE_ENDPOINT`
- API key env vars: `CHUANGZHI_API_KEY`, `NOVACODE_API_KEY`
- endpoint/key source: env-only, execution-time-only
- actual_execution_performed_in_this_commit: `false`
- fallback_allowed: `false`
- gpt-4o fallback: `false`
- source_diagnostic_execution_authorized: `false`
- source_input_read_authorized: `false`
- diagnostics_write_authorized: `false`
- candidate/scorer/performance/Huawei/+3pp: `false`

## Fixed Synthetic Variants

- `baseline_chat_tools_required`
- `chat_tools_auto`
- `chat_tools_required_no_strict`
- `chat_tools_max_completion_tokens`
- `chat_tools_minimal_messages`

The variants are synthetic protocol probes only. They must not read BFCL/source inputs, source manifests, or source diagnostics, and must not include raw prompts, case IDs, gold/expected/reference, scorer diffs, feedback, candidate output, or source metadata.

## Forbidden Outputs

No endpoint/key values, raw request, raw response, raw headers, raw body, provider payload, diagnostics, candidate, scorer, performance, +3pp, or Huawei artifacts may be printed, persisted, or committed.

This commit implements the env-only `--execute-debug` transport path for review but does not run a real provider call.
