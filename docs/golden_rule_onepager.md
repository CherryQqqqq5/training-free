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

Current P0 finding: the important boundary is no longer “schema vs non-schema” in the abstract. The immediate distinction is:

- clarification that should be excluded from true failure counts
- unsupported requests that should stay as policy/capability buckets
- malformed or hallucinated no-tool responses that should become actual compiler targets

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
- response-side tool guard synthesized from unknown-tool and empty-tool evidence
- response-side argument sanitizer synthesized from schema failures
- response-side verification hook synthesized from observed failure classes
- response-side fallback routing synthesized from guard / validation failure patterns

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

## Current Phase-1 Evidence

The current repo already resolved one concrete Phase-1 blocker: noisy failure attribution on baseline traces.

On the `multi_turn_miss_param` baseline traces, the miner now:

- parses bracket-style text tool calls
- parses JSON `action/action_input` text blocks
- excludes prompt-backed clarification requests from true failure counts
- avoids copying stale `validation.empty_tool_call` into mined failures when raw content indicates a different class

After that cleanup pass, the residual mined failures on that subset are a small set of high-value classes rather than a large pool of false `empty_tool_call`.

That changes the next compiler target:

- first target: `hallucinated_completion`
- second target: `malformed_output`
- explicit non-target for forced patching: `unsupported_request`

## Roadmap MVP fields ↔ repository IR

The Phase-1 meeting notes name a JSON/YAML-shaped “golden rule” surface. This repo implements the same semantics under slightly different top-level names (see `src/grc/compiler/ir.py`). Use the table below when writing slides or external specs so vocabulary stays aligned with code.

| Roadmap concept | Where it lives in this repo | Notes |
|-----------------|------------------------------|-------|
| `trigger` | `Rule.trigger` (`MatchSpec`: `tool_names`, `error_types`, `category_patterns`) | Fires on tool id, mined error classes, and optional category hints. |
| `preconditions` | Partially `Rule.scope` + `trigger` | “Must hold before patch applies” is expressed as scope (tools / patch sites) plus match fields, not a separate block yet. |
| `forbidden_actions` | `Rule.action.tool_guard` | Unknown / empty tool handling and guard behavior; not a full arbitrary action grammar. |
| `recommended_tools` | Not a first-class list | Deferred; guard/sanitizer bias tools indirectly. |
| `arg_constraints` | `Rule.action.arg_sanitizer` (`ToolSanitizerSpec` + `FieldConstraint`) | Per-tool field typing, enums, ranges, patterns, defaults. |
| `verification` | `Rule.validation_contract` and `Rule.action.verification` (`VerificationContract`) | Post-parse checks and repair budget; aligns with verification hook. |
| `recovery` | `Rule.action.fallback_router` (`FallbackRoutingSpec`) | Strategy + `on_issue_kinds`; ties to fallback routing in runtime. |
| `stop_condition` | Not explicit | Implicit in BFCL turn limits and proxy pass-through; no dedicated IR field in Phase-1. |

**Failure clustering input** (`FailureIR` in `ir.py`): aggregates `FailureCase` rows from mining—`tool_name`, `error_types`, `field_names`, `expected_types`, `categories`, `trace_ids`, `evidence_count`. That is the bridge from raw traces to `trigger` / sanitizer synthesis.

Canonical names for mined and runtime issue kinds are listed in [failure_taxonomy.md](failure_taxonomy.md).
