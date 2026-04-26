# M2.7ad Fallback Selection

- Passed: `True`
- Old unresolved after repair: `1`
- Fallback recall tradeoffs: `1`
- Unsafe fallback unblocked: `0`
- Activation after guard: `10`

## Cases
- `multi_turn_miss_param_39`: class=`fallback_chain_recall_tradeoff`, action=`diagnostic_only`, selected=`cat` args=`{'file_name': 'test_results.json'}`
  - reason: fallback is risky, but blocking the chain would break M2.7m activation readiness

This is an offline diagnostic only. It does not call BFCL or prove performance.
