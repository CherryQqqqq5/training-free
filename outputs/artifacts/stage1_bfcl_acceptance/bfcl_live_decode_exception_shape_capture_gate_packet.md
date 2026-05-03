# BFCL Live Decode Exception Shape Capture Gate Packet

Status: pending and fail-closed. This prepares a future one-ID live decode exception/field-shape capture gate only; it does not authorize provider access, live capture, BFCL generate, smoke, evaluate, scorer, full/default baseline, candidate paths, performance evidence, +3pp, SOTA, or Huawei claims.

## Requested Future Scope

- Exactly one signed ID: `web_search_base_0`
- Route: `novacode/gpt-4.1`
- Generate-only path sufficient to reach live BFCL parse/decode
- Stop immediately after compact decode/exception shape capture
- No evaluate, scorer, full/default baseline, candidate activation, candidate JSONL/pool, or performance path

## Compact Field Boundary

The packet schema allows only field names listed in `allowed_compact_fields`: route labels, status classes, booleans, counts, and shape labels for provider/proxy/BFCL parse/decode/result classification. It does not allow prompt text, BFCL case content, provider request/response bodies, headers, logs, traces, model output text, tool arguments, gold/reference/expected values, scorer diffs, endpoint/key values, or candidate output.
