# Stage 1 ABHE-v0 Candidate Materialization Plan

This document defines the first two minimal ABHE-v0 candidate materialization plans. They are not executable candidate rules.

`state_tracking_v0` uses a `state_summary_injection` plan. It is limited to multi-turn state carryover failures, requires state carryover evidence, excludes single-turn cases, excludes search or memory watch entries, and does not mutate state.

`hallucination_abstain_v0` uses an `evidence_boundary_verifier` plan. It is limited to answerability failures, excludes valid actionable tool-use cases, tracks false abstain, and must not suppress valid tool calls.

Boundary:
- No candidate rule is generated.
- No candidate YAML is generated.
- No candidate JSONL is generated.
- No candidate pool is created.
- No provider, BFCL, or scorer call is authorized.
- No performance claim is created.

Candidate materialization requires separate candidate spec approval and execution approval.
