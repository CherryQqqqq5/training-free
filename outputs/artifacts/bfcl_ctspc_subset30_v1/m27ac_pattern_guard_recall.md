# M2.7ac Pattern Guard Recall

- Passed: `True`
- Fixed cases blocked: `0`
- Productive non-regression cases blocked: `0`
- After-guard activations: `10`

| Pattern | Regression blocked | Fixed blocked | Productive blocked | Matches | Action |
| --- | ---: | ---: | ---: | ---: | --- |
| `{"baseline_success_proxy":true,"binding_source":"prior_tool_output.cwd_or_listin` | `0` | `0` | `0` | `44` | `diagnostic_only` |
| `{"baseline_success_proxy":true,"binding_source":"prior_tool_output.matches[0]|ba` | `0` | `0` | `0` | `129` | `diagnostic_only` |
| `{"baseline_success_proxy":true,"binding_source":"unknown","postcondition_family"` | `0` | `0` | `0` | `0` | `diagnostic_only` |

This is an offline collateral diagnostic only. It does not call BFCL or prove performance.
