# M2.7w Rule Retention

- Passed: `True`
- Holdout manifest ready: `True`
- Offline U/V readiness: `True`
- Dev scorer net case gain: `-3`
- Decisions: `{'retain': 0, 'demote': 0, 'reject': 3}`
- Regression cases: `4`

Retain remains blocked until holdout scorer evidence exists; negative dev scorer evidence forces regression-causing candidates to reject or record-only.
