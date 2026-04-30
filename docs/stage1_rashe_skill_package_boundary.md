# RASHE Seed Skill Package Boundary

This document fixes the Stage-1 RASHE seed skill package boundary after Step J. It is a research and engineering boundary document only. It does not authorize runtime behavior, source collection, proposer output, candidate generation, scorer execution, BFCL performance evidence, +3pp claims, SOTA claims, or Huawei acceptance claims.

## Current Package Status

The current seed SkillBank is offline-only, default-disabled, and inert.

Allowed at this stage:

- load committed seed skill metadata from the sanitized SkillBank package
- validate metadata, forbidden evidence labels, and no-leakage flags
- route sanitized StepTrace v0.2 records to compact router decisions
- run offline checks and synthetic or approved compact fixtures
- report local counters for router decisions and rejects

Forbidden at this stage:

- prompt injection
- retry behavior
- provider calls
- scorer calls
- BFCL source collection
- candidate JSONL, proposer output, repair output, dev manifest, holdout manifest, or BFCL run artifact creation
- runtime behavior changes in the RuleEngine, proxy, or BFCL execution path
- use of raw traces, raw provider payloads, gold, expected answers, scorer diffs, or holdout/full-suite feedback to write, tune, select, or threshold skills

The router may return a compact decision, but that decision is not an instruction to mutate prompts, execute tools, retry calls, or emit candidates.

## Seed Skill Package

The current seed package consists of four static skills:

- `bfcl_current_turn_focus`
- `bfcl_schema_reading`
- `bfcl_tool_call_format_guard`
- `bfcl_memory_web_search_discipline`

Each skill must remain:

- `offline_only=true`
- `enabled=false`
- `runtime_authorized=false`
- `training_free=true`
- `max_injection_tokens=0`
- `evaluation_status=offline_seed_validated`

The package may define deterministic metadata for future progressive disclosure, including `scope`, `trigger_priority`, `conflicts_with`, `requires_schema`, `requires_current_turn`, and `forbidden_sources`. Those fields are metadata only. They do not authorize disclosure into prompts.

## Forbidden Evidence Taxonomy

Every seed skill must carry exactly the current forbidden evidence taxonomy unless a later research approval changes it:

- `raw_case_identifier`
- `raw_trace_text`
- `raw_provider_payload`
- `gold`
- `expected`
- `scorer_diff`
- `candidate_output`
- `repair_output`
- `holdout_feedback`
- `full_suite_feedback`

These are taxonomy labels, not permission to store or inspect those sources. Checkers should avoid treating taxonomy labels as raw path indicators, but any actual raw field, raw payload, or source path must still be rejected.

## StepTrace v0.2 Input Contract

Router input should be a sanitized StepTrace v0.2 record or an explicitly backward-compatible synthetic fixture. The v0.2 contract is:

| field | requirement | boundary |
| --- | --- | --- |
| `trace_hash` | stable sanitized hash when buffered | no raw trace text |
| `category` | coarse synthetic or approved compact category | no raw case id or split claim |
| `step_index` | local step ordinal | no scorer-derived outcome |
| `state_signature` | compact hash or enum-like state summary | no raw prompt, trace, or provider payload |
| `action_shape` | local action-form summary | no tool output values or gold-derived labels |
| `outcome_local` | local/offline parser or verifier outcome | no scorer diff, expected answer, or holdout/full-suite feedback |
| `skill_tags` | deterministic router tags | no active runtime authorization |
| `source_scope` | source boundary enum | must follow the rules below |

Optional hashes such as `case_hash`, `schema_hash`, and `prompt_hash` are allowed only as hash-like identifiers. Raw `case_id`, raw trace text, raw provider payload, gold, expected, scorer diff, candidate output, and repair output are forbidden recursively.

## Source Scope Rules

Current allowed `source_scope` values:

- `synthetic`
- `approved_compact`

Current rejected `source_scope` values:

- `dev_only_future` - reserved for later explicit approval and disabled now
- any unknown value, including raw/live trace scopes

A non-synthetic compact record requires prior source/real-trace approval before it can be produced or committed. `dev_only_future` cannot be used to generate, select, tune, or threshold skills unless a later approval explicitly changes that boundary. Holdout/full-suite feedback must never be used to generate skills.

## Router Decision Boundary

A router decision is a compact offline decision only. It may contain:

- `selected_skill_id` or a reject status
- `decision_status`
- `reject_reason`
- zero provider/scorer/source counters
- authorization flags that remain false

A router decision must not:

- inject prompt text
- trigger a retry
- call a provider
- call a scorer
- collect BFCL source traces
- emit proposer output or candidate rules
- write dev/holdout manifests
- claim performance improvement

If router input contains forbidden evidence, raw path indicators, unapproved source scopes, or non-zero provider/scorer/source counters, the safe behavior is input reject rather than selection.

## Future Gates

The following gates must remain separate and ordered:

1. source or real-trace approval before any non-synthetic compact records are produced from real traces
2. runtime behavior approval before any router decision can affect prompts, retries, tools, or execution paths
3. proposer/candidate approval before any offline proposer, candidate JSONL, repair rule, dev manifest, or holdout manifest is emitted
4. scorer approval before any BFCL baseline/candidate scoring or paired comparison
5. performance/Huawei approval before any +3pp, SOTA, or acceptance claim

Passing seed skill package checks, StepTraceBuffer checks, or router offline checks is not BFCL performance evidence and does not make Stage-1 +3pp ready.
