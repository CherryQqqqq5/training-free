# Phase-1 failure taxonomy (`error_type` / issue `kind`)

This document is the **single vocabulary** for failure attribution in Phase-1. It matches what `grc mine` emits into `failures.jsonl` and what the runtime records under `validation.issues[].kind` in traces.

## Principles

- **`error_type`** (mining output): string on each `FailureCase` produced by `src/grc/compiler/mine.py` from **raw upstream** responses and from **copied validation issues** already stored in a trace.
- **`kind`** (runtime): string on each `ValidationIssue` produced by `src/grc/runtime/engine.py` and `src/grc/runtime/validator.py` when the proxy processes a response.

For schema and tooling, treat **`error_type` and `kind` as the same namespace** where names overlap: compiler and selector logic key off these strings (see `src/grc/compiler/trace_to_patch.py`).

## Canonical kinds (15)

| # | Name | Typical source | Meaning |
|---|------|----------------|---------|
| 1 | `empty_tool_call` | mine, engine | Request exposes `tools` but the assistant message has no `tool_calls`, and the text is not better explained as clarification, unsupported behavior, malformed output, or hallucinated completion. |
| 2 | `clarification_request` | mine, engine | Assistant asks for missing user parameters before tool invocation; not treated as a true failure bucket for patch synthesis by default. |
| 3 | `natural_language_termination` | mine, engine | Assistant ends the turn in plain language without a tool call and without asking for more information. |
| 4 | `unsupported_request` | mine, engine | Assistant explicitly says the current tool set cannot complete the request. Usually a capability-boundary or fallback-policy bucket, not a schema failure. |
| 5 | `malformed_output` | mine, engine | Assistant output is structurally broken or degenerate, such as a stray symbol instead of a tool call. |
| 6 | `hallucinated_completion` | mine, engine | Assistant claims that an action has already started or completed, but no tool call was emitted. |
| 7 | `wrong_tool_name` | mine, engine | Missing function name on a tool call, or name not in the request tool schema (mined from raw upstream). |
| 8 | `tool_guard_violation` | engine | Post-patch path: tool name not found in the current request schema (often unknown-tool class after routing). |
| 9 | `invalid_json_args` | mine, engine | `function.arguments` string is not parseable JSON. |
| 10 | `non_object_args` | mine, engine | Parsed arguments are not a JSON object (`dict`). |
| 11 | `missing_required` | mine, validator | Required schema field absent from arguments. |
| 12 | `unknown_field` | mine, validator | Argument key not in schema `properties` (when enforced). |
| 13 | `type_mismatch` | mine, validator | Value does not match schema JSON type for a field. |
| 14 | `repair_budget_exceeded` | validator | Repairs exceeded `VerificationContract.max_repairs`. |
| 15 | `validation_issue` | mine (fallback) | Trace contained a validation issue with no `kind`; reserved as generic bucket—avoid writing new rules against it unless the trace is repaired. |

## Mined traces: dynamic `kind`

When `mine.py` ingests `validation.issues` from an existing trace file, it sets `error_type` from `issue["kind"]` when present. Any future engine/validator kind string will flow through automatically. New kinds should be added to this table when they become stable.

## Phase-1 P0 status

The current Phase-1 P0 pass cleaned up a large class of false `empty_tool_call` attributions by:

- recognizing text-form tool calls emitted as bracket syntax
- recognizing JSON `action` / `action_input` blocks
- filtering prompt-backed clarification requests out of mined failures
- ignoring stale `validation.empty_tool_call` when raw content clearly indicates another category

As a result, `empty_tool_call` should now be treated as a **residual bucket**, not the default label for every no-tool response.

## Related code

- Mining: `src/grc/compiler/mine.py`
- Runtime issues: `src/grc/runtime/engine.py`, `src/grc/runtime/validator.py`
- IR row: `FailureCase` / `FailureIR` in `src/grc/compiler/ir.py`
