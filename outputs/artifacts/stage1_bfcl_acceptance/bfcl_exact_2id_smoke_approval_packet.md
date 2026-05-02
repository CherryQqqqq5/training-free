# BFCL Exact 2-ID Smoke Approval Packet

Status: pending/fail-closed. This packet prepares, but does not authorize, one future current-system BFCL-shaped smoke scoped exactly to `web_search_base_0` and `multi_turn_base_0`.

Route is fixed to `novacode` / `gpt-4.1`; fallback, OpenRouter, active `gpt-5.2`, candidate activation, candidate JSONL/pool, full/default BFCL, 8-ID smoke, performance evidence, +3pp, SOTA, and Huawei readiness remain unauthorized.

Only compact smoke artifacts may be considered after separate explicit approval. Raw logs, traces, provider payloads, prompts, gold/reference data, scorer diffs, endpoint values, and key values must not be committed. Stop gates include empty model response, protocol/schema failure, raw leakage, route drift, candidate activation, or any extra ID.

Reviewed generate-only path prepared in this packet:
- Runner: `scripts/run_bfcl_exact_2id_generate_smoke.py`
- Compact artifact checker: `scripts/check_bfcl_exact_2id_generate_smoke_artifact.py`
- Output artifact: `outputs/artifacts/stage1_bfcl_acceptance/bfcl_exact_2id_generate_smoke_compact.json`
- Generate-only remains pending; BFCL evaluate/scorer/full baseline remain unauthorized.
