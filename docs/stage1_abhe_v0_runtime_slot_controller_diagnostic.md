# Stage 1 ABHE-v0 Runtime Slot Controller Diagnostic

This diagnostic replaces prompt/guidance-level miss-param tuning with a bounded
runtime-controller investigation. It does not run full BFCL, does not touch
holdout, and does not create performance evidence.

## Mechanisms

- required_arg_schema_reader_v0: read required slots and types from the intended tool schema.
- valid_tool_call_guard_v0: allow complete valid tool calls and prevent over-blocking.
- prior_tool_observation_slot_binder_v0: bind missing slots only from compatible prior selections or observations.
- prerequisite_lookup_planner_v0: call a prerequisite lookup only when a missing slot is recoverable by an available tool.
- runtime_slot_controller_v2: compose the four primitives into a controller decision.

## Current Gate Result

The synthetic micro-harness validates the controller primitives on compact
fixtures. The offline counterfactual audit reads existing temporary traces and
persists only hash-level, derived labels.

Phase C BFCL rerun is intentionally blocked until runtime_slot_controller_v2 is
integrated into the real proxy request/response path. Running BFCL before that
would only retest prompt guidance and would not validate a runtime controller.

## Evidence Boundary

Committed artifacts contain compact hashes, fixture outcomes, summary counts,
and derived boolean labels only. No raw prompts are committed. No raw trace content is committed. No provider payloads are committed. No gold or expected answers are committed. No scorer diffs are committed. No tool argument values are committed. No raw BFCL result trees are committed. Archive update remains dry-run.
