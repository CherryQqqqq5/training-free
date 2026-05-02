# BFCL Exact 2-ID Smoke Approval Packet

Status: approved for one future generate-only current-system BFCL-shaped smoke scoped exactly to `web_search_base_0` and `multi_turn_base_0`. Provider calls and BFCL generate are authorized only through `scripts/run_bfcl_exact_2id_generate_smoke.py`; BFCL evaluate, scorer, full/default BFCL, 8-ID smoke, candidate activation, candidate JSONL/pool, performance evidence, +3pp, SOTA, and Huawei readiness remain unauthorized.

Route is fixed to `novacode` / `gpt-4.1`; fallback, OpenRouter, active `gpt-5.2`, and `gpt-4o` fallback remain disabled.

Only compact smoke artifacts may be written and checked by `scripts/check_bfcl_exact_2id_generate_smoke_artifact.py`. Raw logs, traces, provider payloads, prompts, gold/reference data, scorer diffs, endpoint values, and key values must not be committed. Stop gates include empty model response, protocol/schema failure, raw leakage, route drift, candidate activation, or any extra ID.

Run-id manifest boundary: this BFCL version reads `test_case_ids_to_generate.json` from the installed BFCL package root. The reviewed runner may temporarily place an exact two-ID manifest at that BFCL-read path during execute mode only, with backup/restore or deletion cleanup in `finally`. The manifest schema is BFCL category to signed ID list: `web_search_base` contains `web_search_base_0`, and `multi_turn_base` contains `multi_turn_base_0`. The legacy top-level `test_case_ids` key is forbidden because BFCL interprets top-level keys as categories. The manifest content is limited to the two signed IDs and contains no raw prompt/case/gold/reference material.


BFCL handler env bridge boundary: execute mode may set `OPENAI_API_KEY` and `OPENAI_BASE_URL` only in the BFCL generate subprocess environment. `OPENAI_API_KEY` is bridged from approved key env names when missing; existing `OPENAI_API_KEY` is preserved. `OPENAI_BASE_URL` is forced in the BFCL generate subprocess to the local OpenAI-compatible proxy `/v1` path for the selected port, even if an inherited shell value exists, so BFCL cannot bypass the reviewed proxy/runtime path. The shell/global environment is not mutated, and endpoint/key values must not be printed or written to artifacts.
