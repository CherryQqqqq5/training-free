# Stage 1 ABHE Granular Approval Review Memo

This memo is for human review of the ABHE approval lanes. It is not an approval packet, execution artifact, candidate artifact, trace artifact, or performance claim.

## Current State

ABHE is ready for granular approval discussion only:

- `abhe_planning_ready=true`
- `abhe_approval_chain_ready_for_review=true`
- `abhe_review_bundle_ready=true`
- `abhe_execution_ready=false`
- `scorer_authorized=false`
- `performance_evidence=false`

No approved packet exists for trace extraction, fresh dev slice materialization, candidate spec approval, or bounded dev smoke execution.

## Recommended Review Order

1. Review `trace_extraction_approval` first.
2. Review `fresh_dev_slice_approval` separately.
3. Review `candidate_spec_approval` after the spec boundary is accepted.
4. Review `execution_approval` last, only after all preconditions are materialized and checked.

## Lane 1: Trace Extraction Approval

Approval lane: `trace_extraction_approval`

If approved, this lane allows:

- Generate a bounded number of sanitized trace cards.
- Write only to the approved trace-card output path.
- Cover only the approved ABHE archive entry ids.
- Use trace cards for mechanism explanation only.

Still forbidden:

- Provider calls.
- BFCL generate or evaluate.
- Scorer execution.
- Candidate generation.
- Candidate rule, YAML, JSONL, or candidate pool creation.
- Performance evidence or archive status promotion.
- Must not persist raw prompt, raw trace, raw payload, raw case id, gold/expected/reference answer, scorer diff, provider exchange, tool argument values, or candidate output.

Required inputs:

- Approved trace extraction packet.
- Approved output path.
- Approved max trace card count.
- Approved target entry ids.
- Existing trace card schema and checker.

Output artifact:

- Sanitized trace cards only, at the approved path.

Checker validation:

- `scripts/check_abhe_trace_extraction_approval_packet.py`
- `scripts/check_abhe_trace_cards.py`
- `scripts/check_abhe_no_leakage_boundary.py`

Failure / rollback:

- Delete or quarantine any nonconforming trace card artifact.
- Keep archive entry status unchanged.
- Re-run trace-card and no-leakage checkers.
- Do not proceed to fresh slice, candidate, scorer, or execution approval based on failed trace extraction.

## Lane 2: Fresh Dev Slice Approval

Approval lane: `fresh_dev_slice_approval`

If approved, this lane allows:

- Approve a fresh dev slice boundary and hash.
- Approve a bounded case count.
- Approve entry ids eligible for future bounded dev smoke review.
- Confirm archive seed evidence is excluded from validation.

Still forbidden:

- Provider calls.
- BFCL generate or evaluate.
- Scorer execution.
- Candidate generation.
- Candidate rule, YAML, JSONL, or candidate pool creation.
- Performance evidence or paired result claims.
- Reuse of the 160 compact discovery cases as validation.

Required inputs:

- Approved fresh dev slice packet.
- Approved fresh dev slice hash.
- Approved case count.
- Approved entry ids.
- Explicit confirmation that archive seed sources are excluded.

Output artifact:

- A fresh dev slice approval record only. The slice itself is not materialized by this memo.

Checker validation:

- `scripts/check_abhe_fresh_dev_slice_approval_packet.py`
- `scripts/check_abhe_fresh_dev_slice_request.py`
- `scripts/check_abhe_execution_readiness.py`

Failure / rollback:

- Reject or revise the approval packet.
- Keep `fresh_dev_slice_materialized=false`.
- Keep execution readiness false.
- Do not proceed to bounded dev smoke review if the slice boundary can overlap discovery evidence.

## Lane 3: Candidate Spec Approval

Approval lane: `candidate_spec_approval`

If approved, this lane allows:

- Approve candidate spec drafts for review progression.
- Record approved spec hashes and entry ids.
- Use approved specs as input to later execution-readiness discussion.

Still forbidden:

- Candidate rule generation.
- Candidate YAML generation.
- Candidate JSONL generation.
- Candidate pool creation.
- Scorer execution.
- Performance evidence.
- Treating spec approval as candidate materialization approval.

Required inputs:

- Candidate spec approval packet.
- Approved candidate spec hashes.
- Approved entry ids.
- Existing candidate spec draft checker.

Output artifact:

- Candidate spec approval record only. No executable candidate artifact is produced.

Checker validation:

- `scripts/check_abhe_candidate_spec_approval_packet.py`
- `scripts/check_abhe_candidate_spec_drafts.py`
- `scripts/check_abhe_execution_readiness.py`

Failure / rollback:

- Keep spec status in review or rejected state.
- Do not generate candidate rules.
- Keep candidate generation authorization false.
- Require a revised spec or separate future candidate materialization approval.

## Lane 4: Execution Approval

Approval lane: `execution_approval`

If approved, this lane allows:

- Authorize bounded dev smoke execution only within approved scope.
- Use approved provider, model, protocol, runtime config, runner manifest hash, candidate spec hash, fresh dev slice hash, and case count.
- Run only the reviewed bounded dev smoke path after execution readiness passes.

Still forbidden:

- Holdout execution.
- Full-suite execution.
- Huawei acceptance claim.
- SOTA or +3pp claim.
- Performance claim beyond bounded dev smoke evidence.
- Any execution if trace extraction, fresh slice, candidate spec, runner manifest, runtime config, or scorer authorization gates are missing.

Required inputs:

- Trace extraction approval status, if trace cards are used.
- Fresh dev slice approval packet.
- Candidate spec approval packet.
- Execution approval packet.
- Runtime config path.
- Runner manifest hash.
- Scorer authorization.
- Approved case count and fresh slice hash.

Output artifact:

- Bounded dev smoke execution approval record. Execution output is separate and must be produced only after the approved command path is run.

Checker validation:

- `scripts/check_abhe_execution_approval_packet.py`
- `scripts/check_abhe_execution_readiness.py`
- `scripts/check_abhe_dev_smoke_packet.py`
- `scripts/check_abhe_dev_smoke_dry_run_manifest.py`
- `scripts/check_abhe_no_leakage_boundary.py`

Failure / rollback:

- Keep `abhe_execution_ready=false`.
- Keep scorer and performance evidence false.
- Reject or revise the execution approval packet.
- Do not run bounded dev smoke until all blockers are cleared by checker evidence.

## Decision Guidance

The lowest-risk first approval is `trace_extraction_approval`, because it can be scoped to sanitized trace cards only and does not authorize provider, BFCL, scorer, candidate generation, fresh slice materialization, or performance evidence.

`fresh_dev_slice_approval` should be reviewed before any dev smoke discussion because it enforces the separation between discovery evidence and validation evidence.

`candidate_spec_approval` should be treated as spec review only. It must not be interpreted as permission to materialize a candidate.

`execution_approval` should be reviewed last. It requires all previous boundaries plus runner, runtime, and scorer readiness to be explicit and machine checked.
