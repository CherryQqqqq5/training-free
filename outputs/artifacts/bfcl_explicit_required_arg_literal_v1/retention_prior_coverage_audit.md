# M2.8-pre Retention Prior Coverage Audit

Offline diagnostic only. This audit does not emit scorer commands and does not relax retain priors.

- Audit ready: `True`
- Explicit prior family coverage zero: `False`
- Coverage conclusion: `explicit_prior_family_has_current_context_coverage`

| Coverage bucket | Count |
| --- | ---: |
| `current_context_anchored_literal_candidate` | `17` |
| `source_result_only_diagnostic_candidate` | `8` |
| `ambiguous_current_context_literal_candidate` | `1` |
| `no_observable_literal_case` | `2626` |

Bucket A requires current request/observation anchoring, unique literal evidence, schema type match, and `demote_candidate` retention prior.
Source-result-only legacy diagnostics remain non-retainable.
