# ABHE-v0 Runtime Slot Observability Plan

## Scope

This is a review-only observability plan. It does not authorize provider calls, BFCL generate/evaluate, scorer, holdout, full suite, candidate JSONL/YAML/rule generation, archive update, or performance claims.

The plan exists because the current runtime slot controller has a score-positive bounded diagnostic result but no confirmed direct slot-bind causality. The next rerun needs better compact attribution before promotion.

## Observability Boundary

Only compact fields may be persisted:

| Stage | Allowed compact fields |
| --- | --- |
| Pre-generation | request patch set hash, adapter projection hash, intended-tool-known flag, required-arg ledger availability, tool schema keyset hash |
| Post-decode | tool-call-present flag, tool-name hash, argument keyset hash, missing-required-arg count before repair, no-tool final-response flag |
| Post-response | existing validator repair kind counts, runtime slot policy hit flag, runtime slot bind repair count, controller-not-applicable reason, argument-keyset-changed flag |

Forbidden material remains forbidden: raw prompts, raw argument values, raw tool schema body, provider payload, raw BFCL result tree, gold/expected/reference answer, scorer diff, endpoint values, API keys, and candidate output text.

## Decision Rule

Do not rerun BFCL to promote `runtime_slot_controller_v2` until the runtime can distinguish:

1. provider-generated valid calls,
2. developer-guidance-induced behavior,
3. existing validator repairs,
4. actual runtime slot bind repairs,
5. no-tool final responses where the slot controller is not applicable.

The next action is a no-provider fixture implementation of this observability path, followed by checker validation. Any BFCL rerun remains a separate approval event.
