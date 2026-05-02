# BFCL Result Materialization Debug Packet

Status: prepared and fail-closed. This packet does not authorize provider requests, BFCL generate, BFCL smoke, BFCL evaluate, scorer, full/default BFCL, candidate activation, candidate JSONL/pool, performance evidence, +3pp, SOTA, or Huawei readiness.

Scope: no-provider synthetic/fake-upstream result materialization debug for the signed IDs `web_search_base_0` and `multi_turn_base_0`, route labels `novacode` / `gpt-4.1`.

Allowed output is compact shape/status flags only. Forbidden material includes raw prompts, raw BFCL case content, raw model output text, tool arguments, provider payloads, logs, traces, endpoint/key values, gold/reference/expected data, scorer diffs, and candidate output.

Prepared variants distinguish: provider/proxy empty output, nonempty proxy tool-call output materialized as empty, nonempty proxy text output materialized as empty, result-file parser missing nonempty output, and BFCL CLI exception-to-empty handling.


Stage 1C extension: a no-provider offline handler/materialization harness may import BFCL handler/decode classes with dummy local env, use synthetic toy response objects, write only temporary synthetic result files, and commit only compact flags/enums. This does not authorize provider requests, BFCL generate/smoke/evaluate, scorer, full baseline, candidate activation, performance, +3pp, or Huawei readiness.
