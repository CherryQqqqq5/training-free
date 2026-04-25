# M2.7n Trace Completeness Diagnostic

- Passed: `True`
- Case-level gate allowed: `True`
- First failed criterion: `None`

| Run | Missing Trace IDs | Unresolved Ambiguity |
| --- | --- | ---: |
| baseline | `[]` | `False` |
| candidate | `[]` | `False` |

## Candidate Case Branches

| Case | Branch | Prefix Traces | Raw Candidates | Ambiguous |
| --- | --- | ---: | ---: | --- |
| multi_turn_miss_param_40 | prompt_prefix_ambiguous_resolved | 21 | 42 | True |
| multi_turn_miss_param_43 | prompt_prefix_ambiguous_resolved | 21 | 42 | True |

This diagnostic is offline only. It does not run BFCL or call an upstream model.
