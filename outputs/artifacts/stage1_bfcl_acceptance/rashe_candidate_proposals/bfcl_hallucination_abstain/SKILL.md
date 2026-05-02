# BFCL Hallucination Abstain

Status: bounded RASHE candidate proposer spec artifact only. This is not a runtime activation, not a scorer input, not performance evidence, and not a Huawei/+3pp claim.

## Provenance

- skill id: `bfcl_hallucination_abstain`
- source diagnostics commit: `cc21c96b70ab51c2bf586c0e79cdde3838dcb05d`
- reviewed approval commit: `b03b155210faaf534ab168bd955fe8e655e83aaa`
- route metadata: `gpt-4.1`
- authorized scope: `bounded_candidate_proposer_execution_only`
- artifact format: `spec_only_no_jsonl_no_pool`

## Compact Evidence

- primary bucket total: `40`
- category coverage count: `2`
- `hallucination`: `unsupported_hallucinated_answer=20`
- `irrelevance`: `irrelevant_tool_call=20`

## Trigger

abstention-safety categories with compact hallucination or irrelevance bucket evidence

## Policy

abstain instead of filling unsupported details; reject if compact evidence coverage is absent or outside signed categories

## Verifier

requires unsupported_hallucinated_answer and irrelevant_tool_call compact counts across the two signed abstention categories and no-leakage audit pass

## Rollback And No-Op Boundary

Remove this spec directory to roll back the proposer artifact. This artifact does not enable runtime behavior, does not create JSONL or pool files, and does not authorize scorer, performance, Huawei, or +3pp workflows.
