# Stage 1 ABHE-v0 Expanded BFCL Dev Analysis

## Scope

This note summarizes the expanded ABHE-v0 BFCL dev smoke and the first refinement loop. It is bounded dev evidence only. It is not full BFCL, not holdout, not a +3pp/SOTA/Huawei acceptance claim, and it does not update the archive.

## Expanded Slice

- Selected case hash: `sha256:e4819b4c639b7fea383ccbe1c73e1591418cce61aceee0ce9a31af21ed2cffe2`
- Case count: 42 compact identifiers
- Strata: `multi_turn_base`, `multi_turn_long_context`, `multi_turn_miss_func`, `multi_turn_miss_param`, `irrelevance`, `live_irrelevance`, `live_relevance`
- Source overlap with archive/discovery evidence: 0
- No raw prompts, gold answers, scorer diffs, provider payloads, or raw BFCL result trees are committed.

## v1 Result

The first expanded candidate kept the relevance/no-tool boundary signal but did not generalize state tracking.

| Entry | Baseline | Candidate v1 | Delta | Interpretation |
| --- | ---: | ---: | ---: | --- |
| state_tracking_v0 | 0/24 | 0/24 | 0 | state summary guidance did not fix expanded multi-turn failures |
| hallucination_abstain_v0 | 6/18 | 18/18 | +12 | no-tool boundary fixed irrelevance/live_irrelevance while retaining live_relevance |
| total | 6/42 | 18/42 | +12 | localized relevance signal, no state-tracking generalization |

Sanitized trace analysis showed repeated compact `post_tool_prose_summary_after_tool_observation` patterns. That points to a continuation/control problem after tool observations, not just missing state-summary text.

## Refinement

The state candidate was refined from a soft state-summary fragment into a compact post-tool continuation guard:

- preserve prior-turn entities, constraints, selected options, and tool-observed state;
- after a tool observation, check whether a pending executable action or prerequisite action remains;
- continue with a needed tool call instead of ending with prose when the tool set can satisfy the request;
- finalize only after required tool actions are complete or no available tool can proceed.

This remains a compact guidance/config-level candidate. It does not generate candidate JSONL/YAML/rules and does not use case identifiers, prompt literals, gold answers, or scorer diffs.

## v2 Result

| Entry | Baseline | Candidate v1 | Candidate v2 | v2 Delta vs Baseline | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| state_tracking_v0 | 0/24 | 0/24 | 12/24 | +12 | post-tool continuation guard has bounded-dev signal, but only half the state strata moved |
| hallucination_abstain_v0 | 6/18 | 18/18 | 18/18 | +12 | relevance/no-tool boundary remains stable on this expanded slice |
| total | 6/42 | 18/42 | 30/42 | +24 | strong expanded-dev signal, still not performance evidence |

State tracking v2 fixed `multi_turn_base` and `multi_turn_miss_func` scorer units, while `multi_turn_long_context` and `multi_turn_miss_param` remain failed in compact category metrics. The right archive action is not broad `dev_passed`; it is to keep the continuation controller and split or narrow the remaining substrata.

## Current Interpretation

ABHE-v0 self-evolution is working in two concrete ways:

1. The archive selected useful behavior clusters: relevance/no-tool boundary and multi-turn state/continuation.
2. Trace-driven refinement improved the candidate from 18/42 to 30/42 on the same expanded dev slice without changing the case hash or using raw case-specific rules.

Weak areas remain:

- State tracking is still mixed. `multi_turn_long_context` and `multi_turn_miss_param` need separate child clusters.
- Current compact metrics are scorer-unit/category level, not strict per-case paired pass/fail.
- The v2 refinement was evaluated on the same expanded dev slice used for diagnosis, so it must be treated as diagnostic. A new fresh dev slice is required before making any broader claim.

## Recommended Next Step

Do not proceed to full BFCL yet. Create a new fresh expanded dev slice or a holdout-style bounded dev slice with no overlap, keep the same v2 candidate, and verify that the +24 compact delta is not slice-specific. Archive update should remain dry-run until that independent verification passes.
