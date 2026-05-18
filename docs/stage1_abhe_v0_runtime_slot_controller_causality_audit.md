# ABHE-v0 Runtime Slot Controller Causality Audit

## Scope

This audit inspects the ABHE-v0 runtime-slot-controller residual run traces from the temporary run directory and writes only compact sanitized counters, hashes, and derived labels. It is bounded residual dev-smoke analysis only. It is not full BFCL, not holdout, not performance evidence, and not an archive update.

Forbidden material remains absent from the committed artifact: no raw prompt literals, no argument values, no provider payloads, no BFCL result tree, no gold/expected/reference answer, no scorer diff, and no candidate output text.

## Main Finding

The score-positive target result is real at the compact scorer-unit level, but direct slot-binder causality is not confirmed.

For `multi_turn_miss_param`:

| Signal | Value |
| --- | ---: |
| conditional_frozen_v2 passed count | 0 |
| runtime_slot_controller_v2 passed count | 24 |
| score delta vs conditional | 24 |
| runtime trace artifacts inspected | 7 |
| runtime marker no-op count | 7 |
| runtime slot bind repair count | 0 |
| runtime slot policy hit count | 0 |
| developer guidance hash equal to conditional | true |
| scorer-unit resolution | category-level, single scorer unit |

The committed causality label is therefore:

`score_positive_but_direct_slot_bind_causality_not_supported`

## Interpretation

The audit weakens the hypothesis that the score gain came from actual runtime slot binding. The runtime arm carried the runtime-slot-controller marker, but no observed trace recorded `abhe_runtime_slot_controller_v2` policy hits or `abhe_runtime_slot_controller_v2_bind_required_slot` repairs.

The audit also weakens a pure developer-guidance explanation for the target category, because the conditional and runtime arms have the same developer-guidance hash for `multi_turn_miss_param`. The remaining plausible causes are:

1. runtime marker or validator-path side effect not captured as a slot repair;
2. provider or sampling variability across arms;
3. scorer-unit/category-level aggregation amplifying arm-level differences;
4. unobserved provider-generated valid tool calls rather than controller-repaired calls;
5. existing repair paths in non-target categories, but not direct target-slot binding.

## Required Next Step

Do not promote `runtime_slot_controller_v2` as a confirmed slot-binding mechanism yet. Before promotion, run a no-provider proxy fixture and same-request no-op replay that proves the controller can create observed bind repairs under the same runtime path. If a future BFCL rerun is used, promotion should require nonzero slot bind repairs plus bounded no-regression controls, not only category-level score movement.
