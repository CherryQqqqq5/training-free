# BFCL materialization empty-after-decode patch gate

Status: pending / fail-closed. This packet prepares review for a future minimal behavior patch only; it does not authorize implementation or execution.

## Causal input

The one-ID post-decode telemetry at commit `e441390c6f417324c242910d5b556ae96842177c` isolated `materialization_empty_after_decode`: BFCL decode returned one executable output, no post-decode exception occurred, materialization was called and wrote a result, the result layout matched, but the materialized shape was `protocol_error_shape` and nonempty detection was false.

## Requested future patch scope

- Preserve nonempty decoded execution output during BFCL measurement/generate result materialization.
- Apply only after nonempty BFCL decode output.
- Do not change provider, route, model, scorer, evaluation, baseline, candidate, or runtime skill behavior.
- Do not change parser/decode unless a separate gate proves it necessary.
- Do not broaden classifier behavior; classifier and protocol-status checks remain downstream validation.

## Offline acceptance criteria

- `execution_list_nonempty` materializes as a nonempty result shape.
- True empty remains empty.
- Protocol exceptions remain `protocol_error`.
- Layout/path classification remains unchanged.
- Compact classifier and protocol-status behavior remain downstream and are not broadened.
- Artifact boundary remains sanitized and contains no endpoint/key material.

## Unauthorized

Provider calls, live telemetry, BFCL generate, BFCL smoke, BFCL evaluate/scorer, full/default baseline, candidate activation, candidate JSONL/pool, scorer-feedback tuning, and performance/+3pp/Huawei paths remain unauthorized.
