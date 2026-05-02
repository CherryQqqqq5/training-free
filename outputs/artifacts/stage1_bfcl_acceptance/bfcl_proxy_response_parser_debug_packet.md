# BFCL Proxy Response Parser Debug Packet

Status: prepared only. This packet authorizes offline synthetic proxy/runtime/parser debug preparation only. It does not authorize provider requests, BFCL smoke, BFCL scorer, full/default baseline, candidate activation, candidate JSONL or pool generation, scorer-feedback tuning, performance evidence, +3pp claim, SOTA claim, or Huawei readiness.

## Scope

The current blocker is repeated `empty_model_response` in the BFCL Responses proxy/runtime path after the synthetic provider contract passed and Responses token-field normalization was fixed. This packet prepares offline synthetic fixtures to distinguish conversion loss, tool-choice/tool-schema loss, engine no-tool text coercion, chat-to-Responses shape loss, and BFCL Responses parser/decode mismatch.

## Output Policy

The offline artifact may contain only compact booleans/enums for shape-level fields. Raw prompt text, raw case content, gold/reference/expected, scorer diff, provider payload, provider response body/header, raw logs/traces, endpoint/key values, source nonce mapping, and candidate output are forbidden.

## Stopped Smoke Facts

The reviewed exact 8-ID BFCL-shaped smoke materialized the signed scope and stopped on repeated `empty_model_response` with observed progress `6/8`. No smoke artifacts, scorer results, performance evidence, +3pp claim, or Huawei readiness were committed.
