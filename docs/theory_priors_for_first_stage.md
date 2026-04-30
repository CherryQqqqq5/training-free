# Theory Priors for First Stage

> Status: superseded as active execution authorization. This document records
> historical rationale for deterministic Stage-1 families. It is not the active
> mainline authorization, not a candidate-pool authorization, and not a
> performance claim. Current evidence shows zero-yield for explicit required-arg
> literal, wrong-key alias, schema-local non-live, structural
> malformed/final-before-tool, raw tool-name/schema normalization, and schema
> retrieval/rerank feasibility. Future work requires scope-change approval; do
> not continue the deterministic candidate-pool sprint under the current gates.

The first-stage research prior is BFCL-first deterministic repair. The goal is
to improve tool-call correctness without training model weights, changing BFCL
evaluator internals, adding hidden model calls, or inventing missing arguments.

This document aligns with `docs/theory_family_retention_ranking.md` and
`docs/bfcl_performance_roadmap.md`. If these disagree, the stricter fail-closed
gate controls execution.

## Priority 1: Deterministic Argument and Tool-Use Repair

This was the historical first-stage deterministic repair prior. It is no longer active mainline authorization after the zero-yield diagnostics.

Allowed families:

1. `explicit_required_arg_literal_completion`
2. `wrong_arg_key_alias_repair`
3. `deterministic_schema_local_non_live_repair`

Rationale:

- BFCL scores concrete tool-call structure, names, and arguments.
- Schema-local repairs can be implemented in the harness and audited before
  scorer execution.
- The repair can be constrained to evidence already present in request/schema or
  source result context.
- Candidate effects are easier to attribute than memory-heavy or soft guidance
  policies.

Retention prior:

- The rule must be schema-local or prompt/source-result anchored.
- The rule must not create new semantic arguments.
- The rule must not require exact tool choice unless separately approved.
- Dev evidence can demote or diagnose; holdout evidence is required before any
  retained-rule claim.

Current blocker:

- Deterministic Stage-1 family search is exhausted under current gates.
- Explicit required-arg literal, wrong-key alias, schema-local non-live,
  structural malformed/final-before-tool, raw tool-name/schema normalization,
  and schema retrieval/rerank feasibility all returned zero-yield or stop-gate
  outcomes.
- Candidate pool, scorer, performance, SOTA/+3pp, and Huawei acceptance claims
  remain unauthorized.

Current route status:

1. Do not continue mechanical source expansion or candidate-pool hunting under
   this deterministic-family plan.
2. `explicit_required_arg_literal_completion` is not a non-zero active family;
   selected-call diagnostics show no missing-required yield.
3. `wrong_arg_key_alias_repair` and
   `deterministic_schema_local_non_live_repair` both returned zero eligible
   candidates in offline diagnostics.
4. Any future route must be approved as a scope change before source expansion,
   scorer execution, candidate generation, or performance claims.

Family-specific constraints:

- `explicit_required_arg_literal_completion` may fill exactly one missing
  required argument only when the value is uniquely grounded in the current
  request or observation and type-checks against schema.
- `wrong_arg_key_alias_repair` may rename one emitted argument key only when the
  alias maps to exactly one schema key and does not alter the value.
- `deterministic_schema_local_non_live_repair` may normalize only schema-local
  values such as numeric strings, booleans, enum casing, JSON-ish strings, or
  safe path forms without changing semantics.

Forbidden:

- Do not source values only from scorer gold or hidden source results.
- Do not fill multiple missing required arguments in one repair rule.
- Do not change tool choice, trajectory order, provider, model, evaluator, or
  BFCL tool schema as part of a candidate repair.
- Do not lower retention priors to inflate candidate count.

This should be written as the first-stage repair program, not as existing
performance evidence for every listed family. Current wrong-key alias and
deterministic schema-local coverage are diagnostic until offline audits show
non-zero, unique, dev/holdout-safe candidates.

## Priority 2: Structured Retry and Output Preservation

This is a secondary engineering route, not the primary first-stage claim.

Candidate scope:

- malformed tool output normalization
- final-before-tool preservation
- structured response compatibility fixes

Rationale:

- These fixes can remove harness/evaluator impedance mismatch.
- They should be reported as compatibility or output-contract evidence unless a
  complete baseline/candidate BFCL comparison proves benchmark uplift.

## Priority 3: Memory Operation Obligation

This is a theory and demo line for training-free self-evolution, not a first-stage
performance mainline.

Current acceptable claim:

- The repo can identify memory-operation obligations.
- The repo can build sanitized review manifests.
- The repo can compile a first-pass guidance-only runtime policy.
- Resolver and activation simulation can block destructive memory tools and avoid
  negative-control activation.

Current disallowed claim:

- Do not claim memory rules improve BFCL.
- Do not claim retained memory.
- Do not run memory-heavy smoke without separate approval, fixed case list,
  provider, baseline command, and candidate command.

## Priority 4: Postcondition Guidance

This line is paused for first-stage performance.

Reason:

- Current dev smoke evidence did not pass stop-loss.
- Source abstraction and scope mismatch make attribution weak.
- Soft guidance was not reliable enough to support a first-stage BFCL claim.

Allowed use:

- Negative-result diagnostics.
- Future source-abstraction design after deterministic argument repair is stable.

## Frozen: CTSPC-v0

CTSPC-v0 is frozen as diagnostic experimental evidence.

Allowed use:

- Explain negative-result audit and fail-closed selection.
- Preserve lessons about regression patterns and scorer feedback mismatch.

Disallowed use:

- Do not use CTSPC-v0 as the first-stage performance route.
- Do not claim BFCL improvement from CTSPC-v0.

Any future CTSPC work must restart from the BFCL performance proof roadmap:
freeze protocol, scan opportunities offline, run a paired subset, then expand
only after positive scorer evidence.

## Engineering Implications

The engineer should not lower retention priors to create apparent coverage.
Current evidence has already driven parser/source-layout, structural, scored
taxonomy, tool-name normalization, and schema retrieval/rerank diagnostics to
zero-yield stop gates. The next valid move is negative-evidence reporting or a
separately approved scope-change review, not continued deterministic candidate
pool expansion.
