# Stage 1 ABHE-v0 Simple Closed Loop

ABHE-v0 is a synthetic/dry-run baseline workflow for showing the closed-loop shape before any provider, BFCL, scorer, real fresh dev slice, or candidate materialization is authorized.

The workflow is intentionally simple:

1. Define a small two-level behavior taxonomy.
2. Score archive entries with a transparent baseline policy.
3. Select the top two proposal-ready entries.
4. Build non-executable candidate spec artifacts.
5. Produce synthetic dev feedback fixtures.
6. Plan archive transitions without updating the archive.

## Scope

Included:

- Two-level taxonomy: broad behavior family and actionable candidate cluster.
- Eight to ten behavior entries.
- Top-2 selection for bounded dev smoke discussion.
- Synthetic candidate specs for `state_tracking_v0` and `hallucination_abstain_v0`.
- Synthetic dev feedback and transition planning.

Excluded:

- Provider calls.
- BFCL generate or evaluate.
- Scorer execution.
- Real fresh dev slice materialization.
- Candidate rule, YAML, JSONL, or candidate pool generation.
- Archive mutation.
- Performance, SOTA, +3pp, or Huawei acceptance claims.

## Baseline Policy

The baseline score is the average of:

- `fixability_prior`
- `mechanism_clarity`
- `safety_prior`
- `readiness`
- `overfit_guard`

The initial `overfit_guard` is `0.5` because ABHE-v0 is still synthetic/dry-run and no approved fresh dev slice is materialized.

The current top two entries are expected to remain:

- `state_tracking_v0`
- `hallucination_abstain_v0`

## Candidate Spec Baseline

`state_tracking_v0` uses a `state_summary_injection` candidate spec:

- Multi-turn only.
- State carryover evidence required.
- Single-turn cases excluded.
- Search/memory watch entries excluded.
- No state mutation.

`hallucination_abstain_v0` uses an `evidence_boundary_verifier` candidate spec:

- Answerability failure only.
- Valid actionable tool-use cases excluded.
- False abstain tracked.
- Must not suppress valid tool calls.

These are not executable candidates. They are spec-only artifacts for synthetic workflow validation.

## Synthetic Feedback

Synthetic feedback is a fixture that exercises the post-dev transition rules. It is not paired dev evidence and does not claim improvement.

The expected transition plan is:

- `state_tracking_v0`: `dev_passed`
- `hallucination_abstain_v0`: `dev_passed`

This demonstrates the archive update mechanism shape only. Real archive state must remain unchanged until an approved bounded dev smoke exists.
