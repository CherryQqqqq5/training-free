# BFCL Multi-Turn State Tracking

Status: bounded RASHE candidate proposer spec artifact only. This is not a runtime activation, not a scorer input, not performance evidence, and not a Huawei/+3pp claim.

## Provenance

- skill id: `bfcl_multi_turn_state_tracking`
- source diagnostics commit: `cc21c96b70ab51c2bf586c0e79cdde3838dcb05d`
- reviewed approval commit: `b03b155210faaf534ab168bd955fe8e655e83aaa`
- route metadata: `gpt-4.1`
- authorized scope: `bounded_candidate_proposer_execution_only`
- artifact format: `spec_only_no_jsonl_no_pool`

## Compact Evidence

- primary bucket total: `80`
- category coverage count: `4`
- `multi_turn_base`: `multi_turn_state_lost=20`
- `multi_turn_long_context`: `multi_turn_state_lost=20`
- `multi_turn_miss_param`: `multi_turn_state_lost=20`
- `multi_turn_miss_func`: `multi_turn_state_lost=20`

## Trigger

multi-turn categories with compact multi_turn_state_lost bucket evidence

## Policy

preserve turn-state commitments before answering; reject if compact evidence coverage is absent or outside signed categories

## Verifier

requires multi_turn_state_lost compact counts across the four signed multi-turn categories and no-leakage audit pass

## Rollback And No-Op Boundary

Remove this spec directory to roll back the proposer artifact. This artifact does not enable runtime behavior, does not create JSONL or pool files, and does not authorize scorer, performance, Huawei, or +3pp workflows.
