# Stage 1 ABHE Fresh Dev Slice Boundary

ABHE requires a fresh dev slice before any bounded dev smoke can be approved.

The 160 compact source cases used for discovery, behavior clustering, archive seeding, and opportunity triage must not be reused as validation evidence. The fresh slice request exists to make that separation reviewable before any execution packet can move forward.

Current request state:

- `approval_status = pending`
- `authorized = false`
- `slice_materialized = false`
- `source_160_compact_cases_reused_for_validation = false`
- `archive_seed_source_excluded = true`
- `fresh_dev_slice_required = true`

Entry scope:

- `state_tracking_v0`
- `hallucination_abstain_v0`

The watch entry `unresolved_search_memory_watch_v0` is excluded from fresh dev smoke. It remains diagnostics-only until split and supported by separate behavior-level evidence.

Forbidden scope:

- No provider call.
- No BFCL generation.
- No BFCL evaluation.
- No scorer.
- No candidate generation.
- No candidate JSONL.
- No performance claim.
- No SOTA/+3pp or Huawei acceptance wording.

`case_list_hash` and `case_count_cap` remain pending until a separate reviewer-approved fresh slice request is accepted. Until then, ABHE is planning/review ready, not execution ready.
