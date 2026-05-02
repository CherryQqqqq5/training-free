# RASHE Provider Route Update Approval Packet

Status: approved route-update artifact only. This packet updates the signed provider model from inactive `gpt-5.2` to fixed `gpt-4.1` based on the synthetic function-calling preflight.

## Route Decision

- route_update_required: `true`
- old_signed_model: `gpt-5.2`
- old_signed_model_status: `unavailable_provider_auth_failed`
- old_signed_model_active: `false`
- new_signed_model: `gpt-4.1`
- provider profile: Chuangzhi/Novacode

The `gpt-4.1` synthetic FC preflight passed: auth, model availability, tool calling, tool choice, and returned tool calls were all true.

`gpt-4o` was observed as supported, but fallback is explicitly forbidden. It is not an execution route.

## Non-Authorization

This route update does not authorize Phase B execution, source diagnostics, candidate generation, scorer execution, performance evidence, +3pp, or Huawei readiness.

Endpoint and key values remain env-only and must not be committed, logged, or written to artifacts.
