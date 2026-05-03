# BFCL Materialization/Classifier After Decode Debug Packet

Status: prepared and fail-closed. This packet authorizes no provider request, live telemetry, BFCL generate, smoke, evaluate, scorer, full/default baseline, candidate path, performance evidence, +3pp, SOTA, or Huawei claim.

## Scope

No-provider synthetic replay for the live-confirmed state where provider/proxy/tool-call shape is present, BFCL parse/decode succeeds with one decoded output, and the remaining label is `materialization_or_classifier_after_decode`.

## Data Boundary

The replay may use only compact decoded-output shape labels from the live capture. It must not use or persist raw arguments, raw tool names, prompts, BFCL case content, provider payloads, logs, traces, endpoint/key values, gold/reference/expected data, scorer diffs, or candidate output.
