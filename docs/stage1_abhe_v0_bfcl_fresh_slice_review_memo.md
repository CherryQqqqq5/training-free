# Stage 1 ABHE-v0 BFCL Fresh Slice Review Memo

This memo is a review entrypoint. It does not approve execution, does not materialize a fresh dev slice, and does not create performance evidence.

## Dataset Path Selection

| field | value |
| --- | --- |
| selected dataset path | `.venv/lib/python3.10/site-packages/bfcl_eval/data` |
| authorized for | `fresh_slice_hash_and_overlap_proof_only` |
| fresh slice materialized | false |
| BFCL generate/evaluate/scorer authorized | false |
| performance evidence | false |

## Approved Strata

| entry_id | approved BFCL strata | proposed compact case count |
| --- | --- | --- |
| `state_tracking_v0` | `multi_turn_base`, `multi_turn_long_context`, `multi_turn_miss_func`, `multi_turn_miss_param` | 10 |
| `hallucination_abstain_v0` | `irrelevance`, `live_irrelevance`, `live_relevance` | 10 |

Search and memory watch entries remain excluded from this top-2 dev smoke proposal.

## Compact Selection Hash Status

| field | value |
| --- | --- |
| proposed selection hash | `sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f` |
| candidate compact case hash count | 20 |
| raw cases persisted | false |
| gold/expected persisted | false |
| scorer diff persisted | false |

Case count by category: `{"irrelevance": 4, "live_irrelevance": 3, "live_relevance": 3, "multi_turn_base": 3, "multi_turn_long_context": 3, "multi_turn_miss_func": 2, "multi_turn_miss_param": 2}`.

## Source Exclusion Proof

| field | value |
| --- | --- |
| overlap check status | `complete` |
| discovery source hash count | 160 |
| candidate case hash count | 20 |
| overlap count | 0 |
| source 160 compact cases reused for validation | false |
| archive seed source excluded | true |

The proof persists compact hashes only. It keeps source text, reference material, scorer deltas, provider payloads, and candidate outputs out of the repo.

## Remaining Human Decisions

1. Review the selected dataset path and the proposed selection hash.
2. Confirm `overlap_count=0` is acceptable for this bounded dev smoke preparation.
3. If acceptable, approve fresh dev slice materialization only in a separate artifact.
4. Keep BFCL execution, scorer, candidate materialization, and performance claims disabled until separately approved.
