# Next Steps — training-free / ABHE-v0

> The first unchecked item is what `project-router` surfaces as your "next step".

- [ ] **review_reduced_batch_alignment_ledger_then_request_retry_approval_if_provider_stable**
- [ ] Per-selected-id / per-turn scorer alignment
- [ ] Reduced batch rerun (verify runner/scorer alignment stable)
- [ ] Rewrite missing-param mechanism as runtime controller (required_arg_schema_reader_v0, valid_tool_call_guard_v0, prior_tool_observation_slot_binder_v0, prerequisite_lookup_planner_v0)
- [ ] Maintain regression suite (no-tool boundary, live_relevance, multi_turn_base)
- [ ] After stable reduced + distinct residual slice → request broader dev → only then full BFCL paired run

## Parking lot
- conditional activation policy for post_tool_continuation_guard_v0
- narrow router for long_context_state_retrieval_v0 (currently causing non-target regressions)
