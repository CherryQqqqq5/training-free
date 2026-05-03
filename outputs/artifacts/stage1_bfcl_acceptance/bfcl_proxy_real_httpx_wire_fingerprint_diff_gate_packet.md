# BFCL Proxy Real HTTPX Wire Fingerprint Diff Gate Packet

Canonical status: pending and fail-closed. This gate is limited to offline/no-provider prepared-request and wire-fingerprint class comparison.

Allowed action after temporary approval: run the synthetic direct-aligned proxy `/v1/responses` adapter path in-process while real `httpx.AsyncClient` sends into `httpx.MockTransport`, capturing only prepared `httpx.Request` class labels. The direct side uses a local fake upstream socket to capture urllib wire-shape labels.

Forbidden: sourcing `/cephfs/qiuyn/.profile`, provider calls, live proxy-to-provider requests, runtime header/trust_env patches, raw request JSON, header values, body bytes, endpoint/full URL/key values, raw response/log/trace/prompt/tool args persistence, BFCL generate/evaluate/scorer/full baseline, source collection, candidate activation, performance/+3pp/Huawei claims.
