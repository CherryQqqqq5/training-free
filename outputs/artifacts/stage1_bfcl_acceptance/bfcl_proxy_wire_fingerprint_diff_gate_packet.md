# BFCL Proxy Wire Fingerprint Diff Gate Packet

Canonical status: pending and fail-closed. This gate is limited to offline/no-provider prepared-request and wire-fingerprint class comparison between the direct urllib path and the proxy diagnostic httpx path.

Allowed action after temporary approval: run the synthetic direct-aligned proxy `/v1/responses` adapter path in-process with fake prepared transport capture, and monkeypatch direct `urllib.request.urlopen` to inspect prepared request metadata. Persist compact labels only.

Forbidden: sourcing `/cephfs/qiuyn/.profile`, provider calls, live proxy-to-provider requests, raw request JSON, header values, body bytes, endpoint/full URL/key values, raw response/log/trace/prompt/tool args persistence, BFCL generate/evaluate/scorer/full baseline, source collection, candidate activation, performance/+3pp/Huawei claims.
