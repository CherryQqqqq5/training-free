# BFCL Classifier Materialized Marker Patch Gate Packet

Status: `pending` and fail-closed. No provider request, live telemetry, BFCL generate, smoke, evaluate, scorer, full baseline, candidate path, performance evidence, +3pp, SOTA, or Huawei acceptance path is authorized.

Future patch scope is limited to the BFCL measurement compact/result classifier: if a materialized entry has `grc_decoded_execution_output_shape`, nonzero decoded output count, and no explicit protocol-error indicator, classify it as generated/nonempty. Explicit handler error phrases, structured error/exception keys, protocol-error indicators, true empty, missing result, and prior generated marker behavior must remain unchanged. Provider, route, parser/decode, scorer/eval/baseline, candidate/runtime skill logic, performance paths, irrelevance unknowns, and broader 8-ID readiness remain out of scope.
