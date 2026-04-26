# M2.7y Scorer Feedback

- Ready: `True`
- Feedback cases: `12`
- Runtime-blocked signatures: `3`
- Fallback contexts: `1`
- Regression cases covered: `True`
- Reason distribution: `{'local_tool_arg_match_but_trajectory_failed': 1, 'proxy_activated_but_scorer_not_activated': 3, 'scorer_arg_mismatch_after_guidance': 1, 'scorer_regression': 4, 'scorer_tool_mismatch_after_guidance': 3}`

This is an offline scorer-feedback overlay. It downgrades regression-causing candidates to record-only and keeps non-regression scorer gaps diagnostic-only; it does not rerun BFCL or prove performance.
