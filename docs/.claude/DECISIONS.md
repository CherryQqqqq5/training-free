# Decisions Log — training-free / ABHE-v0

Append-only. Newest at top.

## 2026-05-19: Hard commit boundaries (sanitized-only)

**Decision**: All artifacts committed to repo MUST be compact / sanitized.

**Forbidden in commits**:
- raw prompt
- gold / expected answer
- scorer diff
- raw provider payload
- raw BFCL result tree
- claims of: dev smoke ≡ full BFCL / +3pp / SOTA / Huawei acceptance

**Why**: Anti-leakage + anti-overclaim. The eval surface is small; any leak destroys generalization signal.

---

## 2026-05-19: ABHE distinguished from generic self-evolution

**Decision**: ABHE-v0 is NOT prompt tuning. It is a fail-closed loop:
```
BFCL failure → behavior-cluster attribution → fresh slice (anti-overfit)
  → materialize compact candidate → bounded paired dev smoke
  → compact feedback → sanitized trace audit → archive dry-run transition
  → next-round candidate mechanism improvement
```

**Alternatives rejected**:
- Generic "generate prompt → score → keep highest" — rejected: doesn't surface which mechanism is the cause.
- Direct full BFCL each iteration — rejected: leakage + cost + no diagnostic granularity.

**Consequences**: Every mechanism candidate must pass bounded eval + trace audit before broader scope.

---

## 2026-05-19: Mechanism promotion gating

**Decision**: Promote a candidate to "stable / regression suite" only when:
- bounded dev shows positive signal
- conditional activation profile is identified (not assumed global)
- trace shows mechanism *actually changes* tool-call structure (not just marker presence)

**Currently NOT promoted**:
- `missing_param_epistemic_gate_v0` (no independent scorer signal)
- `runtime_slot_controller_v2` (marker present but `slot_bind_repair_count=0`)

**Currently considered stable-ish**:
- `no_tool_boundary_v0` (candidate for regression suite)
- `post_tool_continuation_guard_v0` (needs **conditional** activation, not global invariant)
