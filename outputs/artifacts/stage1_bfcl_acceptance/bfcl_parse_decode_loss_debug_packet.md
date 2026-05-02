# BFCL Parse/Decode-Loss Debug Packet

Status: prepared and fail-closed. This packet authorizes no provider request, live telemetry, BFCL generate, smoke, evaluate, scorer, full baseline, candidate path, performance evidence, +3pp claim, SOTA claim, or Huawei claim.

## Scope

Prepare no-provider synthetic BFCL Responses parser/decode-loss isolation for the after-patch one-ID telemetry observation: provider and proxy function-call shape was present, BFCL parse was called and nonempty, but `bfcl_decode_execute_nonempty=false` with `suspected_live_failure_stage=bfcl_parse_decode_loss`.

## Route Boundary

The route remains fixed to `novacode/gpt-4.1`. GPT-4o fallback, active GPT-5.2 route, and OpenRouter are disallowed.

## Data Boundary

Artifacts may contain only booleans, enum labels, counts, and shape labels from synthetic fixtures. They must not contain raw prompts, BFCL case content, provider payloads, logs, traces, raw tool arguments, endpoint/key values, gold/reference/expected data, scorer diffs, or candidate output.
