# M2.7x Scorer-Proxy Gap

- Gap explained: `True`
- Fixed by code change: `False`
- Passed: `False`
- Baseline/Candidate accuracy: `20.0` / `10.0`
- Net case gain: `-3`
- Gap distribution: `{'no_proxy_gap': 19, 'proxy_activated_but_scorer_not_activated': 4, 'proxy_arg_ok_scorer_arg_wrong': 2, 'proxy_ok_trajectory_failed': 2, 'proxy_tool_ok_scorer_tool_wrong': 3}`
- Regressed cases: `4`

This is an offline diagnostic. It explains why source-trace proxy readiness did not become scorer gain; it does not authorize rerun.
