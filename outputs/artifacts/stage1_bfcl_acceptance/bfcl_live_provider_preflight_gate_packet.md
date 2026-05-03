# BFCL Live Provider Preflight Gate Packet

Status: pending. This packet is fail-closed and does not authorize a live provider request until an external temporary packet flips only `approval_status`, `authorized`, `live_provider_preflight_authorized`, and `provider_request_authorized`.

Scope: one synthetic live-provider preflight attempt, compact artifact only, no raw request/response/log/trace persistence, no BFCL generate/evaluate/scorer/full baseline, no candidate activation, no source collection/diagnostics, and no performance/+3pp/Huawei claim.

Endpoint semantics: signed base URL envs `GRC_UPSTREAM_BASE_URL` and `NOVACODE_BASE_URL` are base-url mode and may have `/v1/...` probe paths appended. Signed endpoint envs `CHUANGZHI_NOVACODE_ENDPOINT` and `NOVACODE_ENDPOINT` are full-endpoint mode and must be used as-is; the runner must not append `/v1/...` to them. Artifacts may include env var names and compact mode labels only, never URL or key values.
