# BFCL Live Provider Preflight Gate Packet

Status: pending. This packet is fail-closed and does not authorize a live provider request until an external temporary packet flips only `approval_status`, `authorized`, `live_provider_preflight_authorized`, and `provider_request_authorized`.

Scope: one synthetic live-provider preflight attempt, compact artifact only, no raw request/response/log/trace persistence, no BFCL generate/evaluate/scorer/full baseline, no candidate activation, no source collection/diagnostics, and no performance/+3pp/Huawei claim.

Endpoint semantics: signed base URL envs `GRC_UPSTREAM_BASE_URL` and `NOVACODE_BASE_URL` are base-url mode and may have `/v1/...` probe paths appended. Signed endpoint envs `CHUANGZHI_NOVACODE_ENDPOINT` and `NOVACODE_ENDPOINT` are full-endpoint mode and must be used as-is; the runner must not append `/v1/...` to them. Artifacts may include env var names and compact mode labels only, never URL or key values.
HTTP status semantics: artifacts may include the compact `provider_http_status_label` only, using approved labels such as `status_400`, `status_401`, `status_403`, `status_404`, `status_405`, `status_415`, `status_422`, `status_429`, `other_4xx`, `status_5xx`, `transport_error`, `unknown`, or `not_observed`; they must not include response bodies, headers, URLs, endpoint values, key values, traces, logs, or raw provider payloads.
