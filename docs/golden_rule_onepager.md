# Golden Rule Compiler One-Pager

## Input

Golden Rule Compiler consumes BFCL trace artifacts emitted by the external harness proxy. A trace contains:

- the original OpenAI-compatible `chat.completions` request
- the raw upstream response
- the post-patch response returned to BFCL
- repair events, validation events, latency, and status code

The compiler entry point for Phase-1 is `FailureTrace -> FailureIR -> RuleIR -> PatchBundle`.

## Failure IR

`FailureIR` is the normalized summary of repeated failures extracted from raw trace evidence.

- unit of aggregation: one tool-centric failure cluster
- trigger fields: `tool_name`, `error_types`, `category_patterns`
- evidence fields: `field_names`, `expected_types`, `trace_ids`, `evidence_count`
- purpose: turn noisy request/response traces into a deterministic compiler input

Phase-1 still mines mostly schema-level failures, but the IR already reserves space for verification-hook categories and non-sanitizer triggers.

## Rule IR

`RuleIR` is the explicit intermediate representation used by runtime and selector.

- `trigger`: when the rule should fire
- `scope`: which tools and patch sites the rule can touch
- `action`: the patch payload per site
- `validation_contract`: what counts as a valid post-patch response
- `retention`: where the candidate should move after accept/reject

Phase-1 patch sites are deterministic:

- `prompt_injector`
- `tool_guard`
- `arg_sanitizer`
- `verification_hook`
- `fallback_router`

## Compiler Targets

The compiler does not mutate BFCL internals. It compiles `RuleIR` into an external harness patch bundle consumed by the proxy runtime:

- request-side prompt injection
- response-side tool guard
- response-side argument sanitizer
- response-side verification hook
- response-side fallback routing metadata

The concrete artifact is a YAML `PatchBundle` plus candidate-side metadata files such as `failure_summary.json` and `accept.json`.

## Validation Standard

Phase-1 accepts a candidate only if the candidate metrics dominate baseline on the repo selector criteria:

- accuracy must not decrease
- cost must not increase
- latency must not increase
- subset regressions accumulate into `regression` and must not worsen

Every runtime response also emits a `ValidationRecord` with:

- rule hits
- repair events
- verification issues
- fallback status

This is the contract between compiler output and experimental evaluation.
