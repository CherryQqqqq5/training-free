# RASHE Provider Protocol Debug Preflight Packet

Status: prepared only. This packet does not authorize provider debug execution or Phase B.

## Scope

- signed_model: `gpt-4.1`
- provider_profile: Chuangzhi/Novacode
- approval_status: `prepared`
- execution_authorized: `false`
- provider_request_authorized: `false`
- fallback_allowed: `false`
- gpt-4o fallback: `false`

## Fixed Synthetic Variants

- `baseline_chat_tools_required`
- `chat_tools_auto`
- `chat_tools_required_no_strict`
- `chat_tools_max_completion_tokens`
- `chat_tools_minimal_messages`

The variants are synthetic protocol probes only. They must not read BFCL/source inputs, source manifests, or source diagnostics, and must not include raw prompts, case IDs, gold/expected/reference, scorer diffs, feedback, candidate output, or source metadata.

## Forbidden Outputs

No endpoint/key values, raw request, raw response, raw headers, raw body, provider payload, diagnostics, candidate, scorer, performance, +3pp, or Huawei artifacts may be printed, persisted, or committed.

Execution remains blocked until a later approval changes this packet and runner boundary.
