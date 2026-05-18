# ABHE-v0 Runtime Slot Observability Fixture

## Scope

This fixture is synthetic and no-provider. It exercises `RuleEngine.apply_response()` with the runtime slot controller patch and emits only compact observability labels.

It does not run BFCL generate/evaluate, scorer, holdout, or full suite. It does not update archive and is not performance evidence.

## What It Proves

The fixture proves the compact observability contract can distinguish:

1. a bindable missing required argument repaired by `runtime_slot_controller_v2`,
2. a provider-generated-valid-call proxy that requires no repair,
3. a no-tool final response where the slot controller is not applicable,
4. an ambiguous missing slot where no bind repair should occur.

This is still not BFCL evidence. It is the instrumentation gate needed before any future bounded rerun can be interpreted causally.
