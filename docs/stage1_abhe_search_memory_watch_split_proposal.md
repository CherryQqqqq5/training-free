# Stage 1 ABHE Search/Memory Watch Split Proposal

Parent watch entry: `unresolved_search_memory_watch_v0`

Problem: the current watch entry mixes at least two mechanisms. It must not enter bounded dev smoke or scorer as a single candidate.

Proposed child watch drafts:

- `search_query_or_fetch_failure_watch_v0`
- `memory_retrieve_update_confusion_watch_v0`

Status: diagnostics-only split proposal.

Boundary:

- No scorer.
- No dev smoke.
- No candidate generation.
- No candidate JSONL.
- No provider call.
- No performance claim.

Promotion rule: a child watch draft may become `proposal_ready` only after cross-strata compact evidence or reviewer exception shows a clear behavior cluster, mechanism hypothesis, and bounded candidate direction. BFCL category membership alone is not sufficient.

Rationale: search and memory should remain sampling, reporting, and validation strata until the behavior-level mechanism is separated. This prevents a mixed watch entry from being treated as a direct third dev smoke candidate.
