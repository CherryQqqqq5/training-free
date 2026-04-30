# Training-Free Self-Evolving Agent via Evidence-Guided Rule Compilation

This report describes the first-stage algorithmic claim implemented by the repo.
It is intentionally conservative: the current repository is a scaffold and
diagnostic evidence package, not a completed BFCL performance proof.

Companion documents:

- `docs/first_stage_acceptance_matrix.md`
- `docs/theory_priors_for_first_stage.md`
- `docs/theory_family_retention_ranking.md`
- `docs/bfcl_performance_roadmap.md`


## Current Status Note

Deterministic argument/tool-use repair was the historical Stage-1 mainline, but
it is now exhausted / zero-yield under the approved gates. Provider technical
preflight is green for Chuangzhi/Novacode `gpt-5.2`, but provider green is not
scorer authorization. The direct next step is scope-change decision, not
expanding deterministic argument repair coverage. Current branch status is
diagnostic/negative-evidence handoff only: no source expansion, scorer,
candidate pool, dev/holdout, full-suite, SOTA/+3pp, or Huawei acceptance claim
is authorized.

## Problem

The project targets tool-use failures in agent benchmarks, with BFCL as the
first-stage acceptance benchmark. The system does not train or fine-tune the base
model. Instead, it compiles observed failure evidence into deterministic harness
rules that can be audited, enabled, disabled, and evaluated against the same
benchmark protocol.

## Core Claim

Evidence-Guided Golden Rule Compilation can turn failure traces into external
runtime patches for tool-use behavior while preserving a fail-closed acceptance
boundary.

The intended loop is:

1. Run a BFCL baseline through the external evaluator and local proxy harness.
2. Store request, response, trace, metrics, and manifest evidence.
3. Convert failure traces into a typed failure IR.
4. Compile eligible failures into Golden Rule IR.
5. Materialize rule patches into prompt/tool guard, argument sanitizer,
   verification, fallback, or runtime adapter hooks.
6. Evaluate baseline and candidate under the same BFCL protocol.
7. Retain only candidates that satisfy theory priors and complete dev/holdout
   evidence.

## Why Training-Free

Training-free repair is useful when benchmark failures are caused by tool-call
format, argument realization, missing schema-local normalization, or harness
compatibility rather than absent model knowledge. These failures can often be
addressed outside the model weights and audited more tightly than a prompt-only
or fine-tuning change.

## Golden Rule IR

The Golden Rule surface is a typed intermediate representation for rule patches.
For first-stage BFCL delivery, useful rules must be:

- evidence anchored
- reversible
- runtime scoped
- protocol compatible
- measurable through BFCL metrics
- blocked from retention unless their prior and evidence gates pass

The historical first-stage IR priority was deterministic argument/tool-use
repair because it maps directly to BFCL tool-call correctness. Current evidence
shows that approved deterministic families are exhausted / zero-yield, so this
priority is not an active performance route without scope-change approval.

## Runtime Hook

The repo keeps BFCL evaluator internals external. Runtime changes live in the
proxy/harness layer. This keeps evaluator semantics fixed and makes baseline vs
candidate comparisons meaningful.

Patch sites include:

- argument sanitizer
- tool-call compatibility adapter
- output preservation wrapper
- policy/runtime guidance adapter
- fallback or verification hook

Historically, first-stage acceptance preferred deterministic sanitizer/adapter
hooks over soft guidance when both were available. Current execution requires a
scope-change decision before any new hook family is implemented or scored.

## Retention and Pareto Gate

The selector is not allowed to treat an incomplete run as a zero-score candidate.
Baseline and candidate must both have complete metrics and matching protocol
manifests before comparison.

Candidate retention requires:

- actionable compile status
- protocol-aligned baseline and candidate manifests
- complete metrics
- no forbidden artifact boundary violation
- a satisfied theory prior
- dev and holdout evidence before any retained-rule claim

BFCL score can support a theory-prior candidate, but it cannot create a valid
retention prior after the fact.

## First-Stage Mainline

Historical note: deterministic argument/tool-use repair was the first-stage performance mainline, but it is now exhausted / zero-yield under approved gates:

- `explicit_required_arg_literal_completion`
- `wrong_arg_key_alias_repair`
- `deterministic_schema_local_non_live_repair`

This route remains useful historical rationale, but it is not currently authorized for performance candidate expansion without a scope-change decision.

## Evidence Boundary

Current positive evidence:

- BFCL-first protocol and runner contract are documented.
- M2.8-pre theory-prior gates exist and fail closed.
- Explicit-obligation smoke has an executable manifest but is blocked by dry
  audit and selection gates.
- Memory-operation obligation has strong offline workflow evidence and runtime
  adapter readiness.
- Artifact boundary checks identify raw traces, `.env`, BFCL score/result trees,
  logs, and repair records that must not be in the delivery tree.

Current negative or diagnostic evidence:

- CTSPC-v0 is frozen as diagnostic experimental evidence after negative scorer
  results.
- Postcondition-guided smoke is paused because stop-loss and source-scope gates
  do not support a performance claim.
- Memory-operation evidence does not authorize BFCL scorer or retained-memory
  claims.
- Required next-tool and postcondition policies are useful diagnostics, but
  current evidence does not support a first-stage performance claim.

## Experiment Protocol

The BFCL protocol is fixed by `docs/experiment_protocol_bfcl_v4.md`.

Acceptance comparisons must use:

- same evaluator package and reproduction anchor
- same BFCL model alias
- same upstream profile and model route
- same test category or full-suite scope
- complete baseline and candidate metrics
- recorded run manifests

## Paper Direction

A first paper should present the framework and fail-closed evaluation protocol,
not claim unproven SOTA improvement.

Suggested title:

Training-Free Self-Evolving Agents via Evidence-Guided Rule Compilation

Suggested contributions:

- trace-to-rule compiler for tool-use agents
- Golden Rule IR and runtime patch sites
- BFCL-first fail-closed evaluation protocol
- deterministic argument repair families
- negative-result audits for unsafe or weak repair families

## Patent Directions

Potential patentable directions:

- automatic generation of rollback-safe harness rules from tool-use failure
  traces
- training-free self-evolution gate with theory priors and dev/holdout retention
  control
- capability-obligation runtime policy that repairs missing tool-use behavior
  without argument creation or evaluator modification

## Current Conclusion

The shortest current path is no longer deterministic argument-repair coverage expansion. The valid next step is the scope-change decision memo: either approve one bounded new route or stop the Stage-1 BFCL performance sprint with the diagnostic/negative-evidence handoff.
