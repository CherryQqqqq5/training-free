# ABHE-v0 Runtime Slot Controller Bindability Audit v1

## Scope

This is a compact diagnostic audit. It does not call provider, BFCL generate/evaluate, scorer, holdout, or full suite. It does not update the archive and does not create performance evidence.

The audit reads existing temporary residual-run traces and commits only hash-level counters and enum labels. It does not commit raw prompts, raw tool argument values, provider payloads, BFCL result trees, gold/expected/reference answers, scorer diffs, or candidate output text.

## Question

The previous path replay showed two facts:

1. A no-provider fixture can exercise the runtime path and produce one slot-bind repair.
2. Same-request replay over target BFCL `multi_turn_miss_param` traces is a no-op for slot binding.

This audit explains the second fact by labeling why each target trace does or does not present a bindable missing-slot state at the post-response repair point.

## Reported Labels

Each row contains only compact facts:

- trace artifact hash
- runtime marker presence
- final call origin class
- tool-call counts
- bindability reason counts
- required-keyset and argument-keyset hashes
- source-type counters
- repair/issue/response-shape kind counters

The intended interpretation is narrow: if target traces do not contain bindable missing required arguments, the slot controller cannot be promoted as the causal repair mechanism even when scorer-unit outcomes improve.
