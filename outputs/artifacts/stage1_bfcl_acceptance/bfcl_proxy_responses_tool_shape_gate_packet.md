# BFCL Proxy Responses Tool Shape Gate Packet

Status: pending. This canonical packet is fail-closed and does not authorize a provider request until an external temporary packet flips only `approval_status`, `authorized`, `proxy_responses_tool_shape_authorized`, `local_proxy_request_authorized`, and `provider_request_authorized`.

Scope: one synthetic local proxy `/v1/responses` tool-call shape preflight. The intended future live path is BFCL-style Responses request -> local proxy `/v1/responses` -> one upstream chat-completions request -> compact Responses-envelope shape labels.

Compact boundary: the runner may use temporary traces/logs while deriving labels, but it must delete temporary raw material before writing the compact artifact. The committed artifact may contain labels and booleans only; raw request/response/body/content/header/log/trace/full URL/key/prompt/tool arguments must not persist.

Forbidden: BFCL generate/evaluate, scorer, full/default baseline, source collection/diagnostics, candidate activation/jsonl/pool, performance/+3pp/Huawei claims.
