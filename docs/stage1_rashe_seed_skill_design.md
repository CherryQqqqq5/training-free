# RASHE Seed Skill Progressive Disclosure Design

This document specifies RASHE v0.2 seed skill metadata and progressive disclosure policy for Step G. It is an offline research design artifact only. It does not authorize runtime activation, prompt injection, provider calls, scorer runs, source collection, candidate generation, BFCL performance evidence, SOTA/+3pp claims, or Huawei acceptance claims.

## Design Goal

RASHE uses small static skills to test whether a training-free skill-harness can organize tool-use behavior after deterministic argument/tool repair reached zero-yield. The skill system must preserve no-leakage, avoid case-specific memorization, and expose only minimal relevant guidance when separately authorized in the future.

The current v0/v0.1 seed skills remain the initial SkillBank:

- `bfcl_current_turn_focus`
- `bfcl_schema_reading`
- `bfcl_tool_call_format_guard`
- `bfcl_memory_web_search_discipline`

They are disabled by default and are not active runtime behavior. Step G only defines metadata and routing constraints for progressive disclosure; it does not approve disclosure into prompts.

## Required Skill Metadata

Each seed skill should carry progressive disclosure metadata:

| field | required | meaning | constraints |
| --- | --- | --- | --- |
| `skill_id` | yes | stable skill identifier | no case-specific suffixes |
| `version` | yes | skill version | increment on content or policy change |
| `scope` | yes | categories or situations where skill can be considered | broad class only, not case id |
| `trigger_priority` | yes | deterministic routing priority | integer; lower or higher convention must be documented |
| `max_injection_tokens` | yes | future maximum disclosure size | budget only; no injection authorized now |
| `conflicts_with` | yes | skill IDs that cannot co-activate | used for fail-closed conflict handling |
| `requires_schema` | yes | whether visible tool schema is required | boolean |
| `requires_current_turn` | yes | whether current-turn boundary is required | boolean |
| `forbidden_sources` | yes | data sources the skill must never read | must include gold/expected/scorer diff/raw trace/raw case id |
| `evaluation_status` | yes | `offline_seed`, `offline_fixture_validated`, `runtime_skeleton_only`, or future approved state | cannot imply performance readiness |
| `enabled` | yes | runtime enabled flag | false by default |
| `runtime_authorized` | yes | behavior authorization flag | false until separate approval |

Recommended `evaluation_status` values:

- `offline_seed`: static skill text exists, not validated in runtime
- `offline_fixture_validated`: synthetic fixture coverage exists
- `runtime_skeleton_only`: loadable by inert skeleton, not active behavior
- `dev_only_future`: only after separate dev approval

Forbidden `evaluation_status` values unless formal evidence exists:

- `performance_ready`
- `sota_ready`
- `huawei_ready`
- `holdout_optimized`
- `full_suite_optimized`

## Progressive Disclosure Policy

Default behavior is no injection. The router may produce a proposed skill decision, but that decision is not prompt text, not a retry instruction, not candidate generation, and not runtime behavior.

If future runtime behavior is separately approved, disclosure must obey:

1. Select at most one skill unless a separate multi-skill composition policy is approved.
2. Respect `trigger_priority` only after conflict checks pass.
3. Reject when two or more eligible skills conflict or tie without a deterministic rule.
4. Enforce `max_injection_tokens` before any prompt-side use.
5. Do not include raw examples, case IDs, gold labels, scorer diffs, expected tools, expected arguments, or answer text.
6. Do not use holdout/full-suite feedback to write or tune skill content.

## Router Policy

The router policy for v0.2 is priority plus conflict resolution plus ambiguity rejection:

1. Collect local signals from sanitized StepTraceBuffer records only.
2. Filter skills whose `scope`, `requires_schema`, and `requires_current_turn` constraints are not satisfied.
3. Remove any skill whose `forbidden_sources` would be required by the trace.
4. Sort remaining skills by `trigger_priority`.
5. If top skills conflict through `conflicts_with`, reject with `conflict_reject`.
6. If top priority ties without an approved tie-break, reject with `ambiguous_skill_match`.
7. If exactly one skill remains, return a router decision with `selected_skill_id` but keep `runtime_authorized=false` and `prompt_injection_authorized=false`.

No router output may create candidate rules, dev/holdout manifests, or BFCL run artifacts.

## Skill-Specific Starting Metadata

Suggested initial metadata:

| skill_id | scope | trigger_priority | max_injection_tokens | conflicts_with | requires_schema | requires_current_turn | evaluation_status |
| --- | --- | ---: | ---: | --- | --- | --- | --- |
| `bfcl_current_turn_focus` | multi-turn current-step organization | 10 | 120 | [] | false | true | `offline_fixture_validated` |
| `bfcl_schema_reading` | visible schema interpretation | 20 | 160 | [] | true | false | `offline_fixture_validated` |
| `bfcl_tool_call_format_guard` | local parser/tool-call formatting | 15 | 120 | [] | true | false | `offline_fixture_validated` |
| `bfcl_memory_web_search_discipline` | memory/web-search tool boundary discipline | 30 | 140 | [] | true | true | `offline_fixture_validated` |

These priorities are research defaults only. They do not authorize injection or execution.

## Forbidden Sources

Every seed skill must forbid:

- raw `case_id`
- raw trace or raw provider payload
- gold / expected / reference / possible answer / oracle / checker output
- scorer diff or scorer feedback text
- candidate output or repair output
- holdout/full-suite feedback used for skill generation, routing thresholds, or skill content
- model-generated hidden labels or semantic reranker outputs without separate approval

## Future Gates

Approvals remain separate and ordered:

1. source or real-trace approval before using non-synthetic compact records
2. runtime behavior approval before prompt injection or hook execution
3. candidate generation approval before candidate JSONL or manifests
4. scorer approval before BFCL baseline/candidate scoring
5. performance/Huawei approval before any +3pp, SOTA, or acceptance claim

A seed skill passing offline validation is not BFCL performance evidence, does not make Stage-1 +3pp ready, and cannot be cited as Huawei acceptance evidence.
