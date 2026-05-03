# BFCL Proxy Upstream Conformance Diff Gate Packet

Canonical status: pending and fail-closed. This gate is limited to an offline, no-provider compact conformance/header/policy diff for the proxy upstream-facing request shape.

Allowed action after temporary approval: build one synthetic Responses-style tool-call probe in memory, adapt it to the provider-facing chat-completions shape with fake upstream capture, and write compact labels only.

Forbidden: sourcing `/cephfs/qiuyn/.profile`, provider calls, live proxy requests, raw request/response/header/body/log/trace persistence, prompt or tool-argument persistence, endpoint/key/full URL values, BFCL generate/evaluate/scorer/full baseline, source collection, candidate activation, performance/+3pp/Huawei claims.

The compact artifact may contain only booleans and labels for header shape, message role sequence, policy injection, adapter shape, downstream guards, and suspected 403 cause.
