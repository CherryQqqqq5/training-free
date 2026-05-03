# BFCL one-ID post-decode materialization telemetry gate

Status: approved for exactly one live post-decode materialization telemetry capture on `web_search_base_0`.

## Scope

- Signed ID: `web_search_base_0` only.
- Route: `novacode/gpt-4.1`.
- Future path: generate-only path only as needed to capture compact post-decode, materialization, layout, classifier, and protocol-status flags after successful decode.
- Stop immediately after compact capture.

## Unauthorized

Only provider request, BFCL generate, and live post-decode telemetry are authorized for this one compact capture. BFCL smoke, BFCL evaluate, scorer, full/default baseline, candidate activation, candidate JSONL/pool, scorer-feedback tuning, and performance/+3pp/Huawei paths remain unauthorized.

## Data boundary

Future telemetry may contain only shape flags, enum labels, counts, and path-class labels. It must not contain raw paths, raw prompts, BFCL case content, provider requests or response bodies, response headers, logs, traces, model output text, tool arguments, function names unless separately approved as hashed/shape-only, gold/reference/expected data, scorer diffs, endpoint/key values, or candidate output.

## Compact schema

The allowed compact fields are exactly those listed in `bfcl_one_id_post_decode_materialization_telemetry_gate_packet.json`. The schema must include `suspected_post_decode_failure_stage`.
