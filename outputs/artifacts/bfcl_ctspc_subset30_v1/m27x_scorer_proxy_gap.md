# M2.7x Scorer-Proxy Gap

- Gap explained: `True`
- Fixed by code change: `True`
- Passed: `True`
- Baseline/Candidate accuracy: `20.0` / `13.33`
- Net case gain: `-2`
- Gap distribution: `{'no_proxy_gap': 18, 'proxy_activated_but_scorer_not_activated': 3, 'proxy_arg_ok_scorer_arg_wrong': 2, 'proxy_ok_trajectory_failed': 3, 'proxy_tool_ok_scorer_tool_wrong': 4}`
- Regressed cases: `3`

This is an offline diagnostic. It explains why source-trace proxy readiness did not become scorer gain; it does not authorize rerun.
