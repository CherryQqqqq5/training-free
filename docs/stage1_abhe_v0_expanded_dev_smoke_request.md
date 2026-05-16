# ABHE-v0 Expanded Dev Smoke Request

This document is a review memo, not an approval packet. It requests the next bounded dev step after the same-slice rerun and sanitized trace analysis. It does not authorize BFCL execution, scorer use, holdout, full suite, archive mutation, or any performance claim.

## Current Evidence

| item | status |
| --- | --- |
| Same 20-case selected hash | `sha256:8e28826895c76afd14fb2ec07550b871ea50df25c0666881dad39be86450991f` |
| Same-slice rerun | baseline 8/20, candidate 18/20 |
| Strict scorer-unit fixed/regressed | fixed 3, regressed 0 |
| Scaled compact fixed/regressed | fixed 10, regressed 0 |
| Trace boundary | sanitized only; raw material absent |
| Claim boundary | bounded dev smoke only; no full BFCL performance claim |

The same-slice rerun supports a next expanded dev review, not a full BFCL run. It also shows sub-lane instability: `live_irrelevance` was not fixed in the prior run but was fixed in the rerun, while `multi_turn_miss_func` remains an unchanged failure in the rerun. These deltas require expansion before archive mutation.

## Requested Expanded Dev Scope

| entry | strata | requested cap |
| --- | --- | --- |
| `state_tracking_v0` | `multi_turn_base`, `multi_turn_long_context`, `multi_turn_miss_func`, `multi_turn_miss_param` | 5-10 per stratum |
| `hallucination_abstain_v0` | `irrelevance`, `live_irrelevance`, `live_relevance` | 5-10 per stratum |

Total requested scope is 40-60 fresh dev cases. A new selected case hash and source exclusion proof are required before any execution discussion.

## Split Interpretation

| lane | current interpretation | next action |
| --- | --- | --- |
| `state_tracking_v0` | bounded-dev positive signal, but not all multi-turn subtypes fixed | verify on expanded dev before archive write |
| `irrelevance_no_tool_boundary_v0` | positive bounded-dev signal | verify on expanded dev |
| `live_irrelevance_boundary_v0` | signal changed between runs | split and verify, do not treat as unconditional pass |
| `live_relevance_guard_v0` | unchanged pass, no false-abstain signal | retain as guard |

## Stop-Loss

Execution must stop before or during expanded dev if any of these occur: source overlap, selected hash mismatch, provider/model/protocol mismatch, entry-specific activation missing, raw leakage, compact regression, false abstain, valid tool-call suppression, cost delta above 5 percent, latency delta above 20 percent, or any holdout/full-suite attempt.

## Still Forbidden

Provider/BFCL/scorer execution for expanded dev is not approved by this memo. Candidate JSONL/YAML/rule generation, raw prompt or gold persistence, archive mutation, holdout, full suite, SOTA/+3pp, Huawei acceptance, and performance claims remain forbidden.
