# Stage 1 ABHE-v0 BFCL Fresh Slice Review Memo

This memo is a review entrypoint. It does not approve execution, does not materialize a fresh dev slice, and does not create performance evidence.

## Dataset Path Candidates

| candidate | status | review note |
| --- | --- | --- |
| `.venv/lib/python3.10/site-packages/bfcl_eval/data` | exists | Installed BFCL package data directory with BFCL_v4 category JSON files. Reviewer must confirm this is the intended sprint BFCL version before selection. |
| `outputs/bfcl_v4` | exists | Repo output directory candidate; currently not selected. |
| `outputs/artifacts/bfcl_ctspc_source_pool_v1` | exists | Historical source/artifact pool, not recommended for fresh validation because it may overlap discovery/source evidence. |

## Proposed Strata

| entry_id | proposed BFCL strata | proposed case count |
| --- | --- | --- |
| `state_tracking_v0` | `BFCL_v4_multi_turn_base`, `BFCL_v4_multi_turn_long_context`, `BFCL_v4_multi_turn_miss_func`, `BFCL_v4_multi_turn_miss_param` | 10 |
| `hallucination_abstain_v0` | `BFCL_v4_irrelevance`, `BFCL_v4_live_irrelevance`, `BFCL_v4_live_relevance` | 10 |

Search and memory watch entries remain excluded from this top-2 dev smoke proposal.

## Source Exclusion

The discovery/archive-seed compact source count is derived from the existing RASHE compact source input files. The candidate BFCL case hashes are not computed yet because no reviewer-selected dataset path exists.

Current overlap proof status: blocked, with blocker `bfcl_dataset_path_not_selected`.

## Hash Status

`proposed_selected_case_ids_hash` is pending until reviewer selects the BFCL dataset path. After selection, only compact identifiers and hashes should be persisted.

## Remaining Human Decisions

1. Select the BFCL dataset path candidate.
2. Confirm the proposed strata match `state_tracking_v0` and `hallucination_abstain_v0`.
3. Confirm 10 + 10 cases is the correct first bounded dev smoke size.
4. Approve fresh dev slice materialization only, if the above are acceptable.
5. Keep execution readiness false until materialization, candidate approval, runtime config, provider/model/protocol, and bounded scorer authorization are separately approved.
