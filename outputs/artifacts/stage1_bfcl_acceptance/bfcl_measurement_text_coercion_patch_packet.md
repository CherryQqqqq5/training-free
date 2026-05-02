# BFCL Measurement Text Coercion Patch Packet

Status: prepared/fail-closed. This packet records a measurement-only runtime policy change: nonempty no-tool text responses in `configs/runtime_bfcl_structured.yaml` are record-only and must not be blanked into `empty_model_response`. True empty upstream responses remain empty and distinguishable.

This packet does not authorize provider requests, live telemetry, BFCL smoke, BFCL scorer, full/default baseline, candidate runtime activation, candidate JSONL/pool, performance evidence, +3pp, SOTA, or Huawei readiness.

No raw prompt/case/gold/reference/scorer diff/provider payload/log/trace/endpoint/key material is authorized or persisted.
