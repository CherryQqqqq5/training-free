# Phase-2 Design Draft

## 0. Objective

Phase-2 must solve the main failure mode left after Phase-1 hardening:

- the system can reliably detect failures
- but it cannot yet reliably turn high-value behavioral failures into performance gains

Phase-2 therefore targets:

- decision-policy synthesis
- historical candidate reuse
- outer-loop search
- anti-overfitting validation

This phase should move the repository from:

- reliable compatibility harness

to:

- self-evolving decision-policy harness

## 1. Design Principles

Phase-2 changes must satisfy all of the following.

### 1.1 Solve decision failures, not only shape failures

Primary target failures:

- `empty_tool_call`
- `hallucinated_completion`
- `natural_language_termination`
- `redundant_clarification_request`

Secondary target failures:

- selected `malformed_output`
- selected `unsupported_request` only when clearly misclassified and locally recoverable

### 1.2 Keep rules request-local

No rule should globally inject broad instructions without a local trigger.

Every request-side policy patch must have:

- explicit request-local predicate(s)
- explicit intended effect
- explicit stop / continue semantics

### 1.3 Separate compatibility from capability

Phase-2 must maintain two distinct comparison lines:

- `compatibility_baseline`
- `compiler_patch_candidate`

No Phase-2 claim should attribute gains from protocol compatibility to self-evolution.

### 1.4 Optimize for cross-subset transfer

Patches should not be accepted only because they help one BFCL slice.

Acceptance must continue to require:

- no artifact regression
- no significant cross-subset score regression
- no protocol / manifest drift

## 2. Required IR Extensions

Current IR is adequate for sanitization and verification, but not for decision repair.

Phase-2 should extend [src/grc/compiler/ir.py](/Users/cherry/.codex/worktrees/3253/training-free/src/grc/compiler/ir.py) with first-class decision fields.

### 2.1 New trigger / predicate surface

Add request-local predicate support:

- `request_predicates`
  - tools available
  - user ask unresolved
  - prior tool output present
  - latest assistant output prose-only
  - prior explicit literal exists
  - evidence missing for final answer

These should be explicit, serializable, and testable.

### 2.2 New decision-policy fields

Add:

- `recommended_tools`
- `continue_condition`
- `stop_condition`
- `forbidden_terminations`
- `evidence_requirements`

Meaning:

- `recommended_tools`: candidate next-action tools under local conditions
- `continue_condition`: when the agent must keep acting
- `stop_condition`: when the agent is allowed to terminate
- `forbidden_terminations`: patterns that are not acceptable endings
- `evidence_requirements`: proof required before final answer is allowed

These are not BFCL-specific concepts. They are generic agent-control abstractions.

## 3. Compiler Upgrades

Phase-2 compiler work should focus on synthesizing decision-policy patches rather than only defensive patches.

### 3.1 New synthesis templates

Introduce explicit templates for:

#### A. `empty_tool_call -> continue-execution`

Compiler output should include:

- request predicates
- recommended tools
- continue condition
- optional constrained retry behavior

Example semantics:

- if tools are available
- and prior tool outputs do not yet satisfy the user request
- and the last assistant response is prose-only
- then bias next step toward a tool call instead of explanation

#### B. `hallucinated_completion -> evidence-before-completion`

Compiler output should include:

- forbidden terminations
- evidence requirements
- stop condition

Example semantics:

- final answer is disallowed unless required evidence has appeared in tool outputs

#### C. `natural_language_termination -> structured continuation`

Compiler output should include:

- continue condition
- allowed completion surface
- recommended tool family

Example semantics:

- prose summary is not enough while task state is unresolved

#### D. `redundant_clarification_request -> literal reuse`

Compiler output should include:

- request predicates for context-literal reuse
- preferred argument source
- clarification suppression condition

Example semantics:

- if the needed value is already explicit in conversation state or recent tool results, do not ask the user again

### 3.2 Global failure rules must become localizable

Phase-2 should not simply enable global prompt injection.

Instead:

- global failures may only become request-side rules if the compiler can synthesize request-local predicates
- otherwise they remain analysis artifacts, not live runtime policies

This avoids:

- prompt pollution
- benchmark overfit
- broad regression from always-on behavioral instructions

## 4. Runtime Architecture Changes

Phase-2 should split runtime behavior into two distinct layers.

### 4.1 Compatibility layer

Keep current compatibility behavior:

- prose-to-empty coercion when needed for evaluator safety
- structured tool-call recovery from high-confidence text
- BFCL request-shape compatibility
- layout and trace consistency

This layer exists to make runs trustworthy.

### 4.2 Policy layer

Add a separate request-time policy layer driven by the new IR.

Capabilities:

- evaluate request predicates
- inject scoped decision guidance
- suppress early stop when continue condition holds
- gate final answer when evidence requirements are unmet
- prioritize locally recommended tools

Important constraint:

- policy actions must be scoped and reversible
- no broad always-on patching

## 5. Outer-Loop Search

This is the key missing self-evolution capability.

### 5.1 Historical candidate memory

Persist searchable memory over:

- accepted candidates
- rejected candidates
- incomplete candidates
- compile failures

Index by:

- failure signature
- subset family
- rule shape
- outcome summary
- regression profile

### 5.2 Proposal retrieval

When a new failure cluster appears:

- retrieve similar prior failure signatures
- retrieve accepted and rejected patch shapes
- propose:
  - reuse
  - specialization
  - composition
  - mutation

This turns patch generation into search rather than one-shot synthesis.

### 5.3 Credit assignment

Selector output should feed a proposal prior:

- which patch families helped
- which patch families harmed
- which subsets were sensitive
- which failure classes remain uncompilable

The selector remains the judge, but Phase-2 adds a teacher path built from its outcomes.

## 6. Offline Simulator / LLM Critic

Phase-2 should not add a fake online user to official BFCL runs.

Instead, use an offline simulator or LLM critic for proposal ranking.

### 6.1 Allowed uses

- generate counterfactual next actions for failure traces
- estimate whether a candidate patch changes prose-only steps into tool steps
- rank candidate policies before expensive benchmark runs
- synthesize candidate stop / continue conditions from trace evidence

### 6.2 Disallowed use

- do not insert simulator replies into benchmark-time execution

Reason:

- that would change the protocol being evaluated
- it risks optimizing to an artificial interaction loop

The simulator should act as:

- critic
- cheap rollout evaluator
- proposal teacher

not:

- benchmark-time user replacement

## 7. Reuse Redefinition

Phase-2 reuse should mean policy reuse, not artifact reuse.

The reusable units should be:

- failure clusters
- accepted patch fragments
- rejected patch anti-patterns
- request predicates
- stop / continue templates

The question should not be:

- "is this task similar?"

It should be:

- "have we already learned how to repair this failure family?"

## 8. Anti-Overfitting Constraints

Phase-2 must hard-code guardrails against benchmark overfit.

### 8.1 Rule admissibility

A request-side policy rule is admissible only if:

- it has explicit request-local predicates
- it is grounded in tool schema and runtime evidence
- it does not mention benchmark IDs or category-specific case names

### 8.2 Candidate acceptance

Candidate acceptance continues to require:

- `compile_status = actionable_patch`
- `evaluation_status = complete`
- manifest consistency
- Pareto-style non-regression

Additionally for Phase-2:

- reject candidates that improve only one slice while worsening another tracked slice beyond threshold

### 8.3 Proposal evaluation

Do not accept a patch solely because it matches a mined failure pattern.

Require:

- evidence that the patch changes next-action behavior
- evidence that the patch does not simply hide errors by coercion

### 8.4 Reporting split

Every report must separate:

- compatibility gains
- decision-policy gains

This is necessary to avoid false claims that the compiler has learned when only the adapter improved.

## 9. Minimal Viable Phase-2

The smallest credible Phase-2 implementation should not try to solve everything at once.

Recommended MVP:

### MVP target

Only target:

- `empty_tool_call`

### MVP additions

- add `request_predicates`
- add `recommended_tools`
- add `continue_condition`
- add `stop_condition`
- add one compiler template:
  - `empty_tool_call -> continue-execution`
- add request-side policy application in runtime for rules with predicates
- add historical memory for accepted/rejected `empty_tool_call` patches only

### MVP evaluation

Primary benchmark:

- `multi_turn_miss_param`

Safety checks:

- `simple_python`
- at least one additional harder slice after local success

Success criterion:

- reduce `empty_tool_call` materially
- improve `multi_turn_miss_param`
- do not regress clean subsets significantly

## 10. File-Level Implementation Map

Expected main touch points:

- [src/grc/compiler/ir.py](/Users/cherry/.codex/worktrees/3253/training-free/src/grc/compiler/ir.py)
  - add new decision-policy fields
- [src/grc/compiler/trace_to_patch.py](/Users/cherry/.codex/worktrees/3253/training-free/src/grc/compiler/trace_to_patch.py)
  - synthesize decision-policy rules for high-value failures
- [src/grc/runtime/engine.py](/Users/cherry/.codex/worktrees/3253/training-free/src/grc/runtime/engine.py)
  - evaluate request predicates and apply policy-layer logic
- [src/grc/selector/pareto.py](/Users/cherry/.codex/worktrees/3253/training-free/src/grc/selector/pareto.py)
  - remain selector, but expose stronger rejection reasons to proposal memory
- new proposal-memory module under `src/grc/selector/` or `src/grc/compiler/`
  - historical patch retrieval and ranking
- new offline critic / simulator helper under `src/grc/compiler/` or `src/grc/utils/`
  - proposal ranking only, not online benchmark execution

## 11. Expected Outcome

If implemented correctly, Phase-2 should change the system in a measurable way:

- fewer prose-only tool-enabled turns
- fewer early stops
- fewer unsupported "I already did it" completions
- more successful continuation on harder BFCL slices

What Phase-2 does not promise:

- immediate universal gains on every subset
- elimination of model limitations
- automatic planner quality without explicit decision IR

What Phase-2 should realistically deliver:

- the first version of a true self-evolving outer loop
- policy reuse across failure families
- measurable movement on behavior-dominant BFCL slices
