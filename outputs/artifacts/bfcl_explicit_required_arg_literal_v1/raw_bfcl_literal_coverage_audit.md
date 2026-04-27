# M2.8-pre Raw BFCL Literal Coverage Audit

Offline diagnostic only. Source-result tool args are audited against raw BFCL prompts; they are not treated as retain-prior evidence.

- Audit ready: `True`
- Source-result diagnostic literals: `25`
- Prompt/observation anchored literals: `17`
- Retain-prior candidates under raw prompt audit: `1`
- Route recommendation: `fix_current_context_literal_extractor`

| Failure reason | Count |
| --- | ---: |
| `ambiguous` | `16` |
| `scanner_missed` | `1` |
| `source_result_only` | `8` |

No scorer commands are emitted.
