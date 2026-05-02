# BFCL One-ID Live-Shape Telemetry Gate Packet

Status: approved for exactly one one-ID live-shape telemetry execution scope. This authorizes provider request and BFCL generate only for compact telemetry on `web_search_base_0`; it does not authorize BFCL smoke, BFCL evaluate/scorer, full/default baseline, candidate activation, candidate JSONL/pool, scorer-feedback tuning, performance evidence, +3pp, or Huawei readiness.

## Requested Future Scope

- Scope: one live-shape BFCL generate-only telemetry probe under the reviewed one-ID telemetry gate.
- Signed run ID: `web_search_base_0`.
- Route: `novacode` / `gpt-4.1`; fallback, OpenRouter, active `gpt-5.2`, and `gpt-4o` fallback are disabled.
- Output policy: compact shape flags and enum labels only.
- Candidate specs remain inert.

## Allowed Future Telemetry Fields

The future artifact may contain only the field names listed in the JSON packet under `allowed_telemetry_fields`. The fields are shape/status labels only and are intended to locate where the live BFCL-shaped path becomes empty.

## Forbidden Content

No raw prompt text, BFCL case content, provider request, provider response body, response headers, logs, traces, model output text, tool arguments, gold/reference/expected material, scorer diff, endpoint/key values, source nonce mapping, or candidate output may be written.

## Current Evidence Boundary

Offline handler decode, result materialization, compact classifier, and exception-to-empty paths did not reproduce the live exact-BFCL empty blocker. This packet authorizes only the reviewed one-ID telemetry gate state; it is not measurement evidence and does not authorize a patch, smoke, scorer, baseline, candidate, or performance path.

## Execution Scaffold Requirements

The reviewed scaffold must validate compact artifacts with `scripts/check_bfcl_one_id_live_shape_telemetry_artifact.py`. Future telemetry must include protocol exception flags and classifier false-empty flags: `protocol_exception_observed`, `protocol_exception_converted_to_empty_model_response`, and `classifier_false_empty_for_nonempty_result`. Protocol exceptions must remain distinguishable from `empty_model_response`; nonempty result material must not be classified as empty.

## Signed Capture Boundary

Signed live-capture factory: `scripts.bfcl_one_id_live_shape_telemetry_capture:build_signed_one_id_live_shape_capture`. Unsigned capture factories are not allowed. The factory is bounded to `web_search_base_0`, `novacode/gpt-4.1`, generate-only shape telemetry, compact fields only, and no evaluate/scorer/baseline/candidate/performance path.
