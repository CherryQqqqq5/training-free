# BFCL Measurement Anti-Overfit Design Packet

Status: `pending` / fail-closed. This packet records measurement design only. It does not authorize scorer execution, provider calls, candidate generation, candidate JSONL, candidate pools, runtime activation, performance evidence, +3pp claims, SOTA claims, or Huawei readiness.

## Freeze Source Of Hypothesis

Phase B compact 8x20 diagnostics remain hypothesis generation only. They must not be used as final performance evidence.

- target_commit_for_measurement: `94f2546d52e0e2b06d8e24630f7714fc8bbe475c`
- proposer_artifact_commit: `e73900fc7553735e5dbf5121fc46d3ead44c5077`
- route: `Chuangzhi/Novacode` / `gpt-4.1`

## Split Discipline

- dev/tuning split: may be used only after explicit integration authorization.
- holdout/full split: measurement only; no feedback to proposer/runtime.
- per-case scorer diff: must not be used to modify proposals unless a new tuning gate is approved.

## Negative Controls For Future Integration

- `simple`
- `multiple`
- `parallel`
- `parallel_multiple`
- multi-turn correction/override cases
- abstention false-positive cases

## Ablation Plan

A. frozen current system, no candidate activation
B. `bfcl_multi_turn_state_tracking` only
C. `bfcl_hallucination_abstain` only
D. both combined

## Overfit Blockers

- reject if improvement appears only in the source diagnostic categories
- reject if abstention false positives increase
- reject if simple/multiple/parallel regress beyond threshold
- reject if holdout delta is materially lower than dev delta
- reject if scorer feedback was used before freezing holdout

## Forbidden Material

Raw prompt, trace, provider request/response, case ID, gold, expected, reference, scorer diff, candidate output, repair feedback, holdout/full feedback, endpoint/key material, and source nonce mapping are forbidden.
