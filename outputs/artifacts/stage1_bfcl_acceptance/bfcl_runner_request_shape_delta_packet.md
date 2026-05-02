# BFCL Runner Request Shape Delta Packet

Status: prepared / fail-closed. This packet authorizes only no-provider, shape-only comparison between the reviewed live-shape telemetry path and the exact reviewed BFCL smoke runner/request path.

It does not authorize provider requests, live telemetry reruns, BFCL smoke, BFCL scorer, full/default baseline, candidate activation, candidate JSONL/pool, scorer-feedback tuning, performance evidence, +3pp, SOTA, or Huawei readiness.

Scope:
- route: novacode / gpt-4.1
- telemetry artifact: outputs/artifacts/stage1_bfcl_acceptance/bfcl_live_shape_telemetry_compact.json
- smoke run-id manifest: outputs/artifacts/stage1_bfcl_acceptance/bfcl_stage1_smoke_run_id_manifest.json
- delta artifact: outputs/artifacts/stage1_bfcl_acceptance/bfcl_runner_request_shape_delta.json
- output policy: compact shape labels and buckets only

No endpoint/key values, provider bodies, headers, logs, traces, BFCL case content, gold/reference/expected material, scorer diffs, or candidate outputs may be written.
