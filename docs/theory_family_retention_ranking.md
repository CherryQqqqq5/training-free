# Theory-Guided Retention Ranking

This memo records the current retain decision logic for the first Huawei delivery phase. It is intentionally theory-first: BFCL can validate or falsify a proposed family, but BFCL score cannot create a retained rule.

## Retain Rule Definition

A rule is not retained unless all three conditions hold:

1. It belongs to a theory-prior family with explicit preconditions, postconditions, and exclusions.
2. It has positive dev scorer evidence without unacceptable regressions.
3. It has holdout scorer evidence. Without holdout, the maximum state is `demote_candidate`.

Current project status: `retain=0`. This is correct. There is no BFCL dev+holdout evidence yet.

## Ranked Families

### 1. memory_first_pass_retrieve_soft_v1

Status: first retain candidate, not retained.

Why it is first:

- It targets BFCL V4 memory behavior rather than file/path trajectory forcing.
- It is a policy over observable memory-witness state, not a case-specific patch.
- It is guidance-only, capability-only, argument-free, no exact tool choice.
- It blocks destructive memory operations and excludes weak-witness cases from first-pass compilation.

Theory prior:

```text
If the user requests durable memory information, memory tools are available, and the current trajectory has no strong memory value witness, the agent should attempt a schema-available memory retrieval capability before answering from prose alone.
```

Offline evidence:

```text
memory_operation_candidate_count = 78
first_pass_compiler_allowlist = 48
weak_witness_compiler_input = 0
dry_run_policy_unit_count = 1
resolver_scanned/resolved = 48/48
forbidden_memory_mutation_tools_resolved = 0
activation_simulation_count = 48
negative_control_activation_count = 0
argument_creation_count = 0
```

Why not retain yet:

- No runtime adapter is currently loaded by the BFCL candidate runner.
- No dev scorer evidence exists for the memory policy.
- No holdout evidence exists.

### 2. explicit_required_arg_literal_completion

Status: valid but insufficient coverage.

Evidence:

```text
retain_eligible_candidate_count = 17
```

This family is clean: argument-only, current-context grounded, no tool-choice mutation. It is kept as a low-risk pool component, but it is too small to support dev20/holdout20 by itself.

### 3. wrong_arg_key_alias_repair

Status: theory-valid, current source coverage zero.

Evidence:

```text
wrong_arg_key_alias_demote_candidate_count = 0
wrong_arg_key_alias_family_coverage_zero = true
```

The theory is sound, but current baseline emitted args are mostly already canonical or unparseable for unique alias repair. Do not pursue as the short-term performance line.

### 4. deterministic_schema_local_non_live_repair

Status: theory-valid, current source coverage zero.

Evidence:

```text
deterministic_schema_local_demote_candidate_count = 0
deterministic_schema_local_family_coverage_zero = true
```

This remains diagnostic unless parser/source-layout audits show an implementation gap.

### 5. CTSPC-v0 file/path multi-turn

Status: frozen diagnostic scaffold.

Reason: repeated durable dev scorer failures showed negative net gain and mixed regression sources (`action_policy`, `no_tool_repair`, `trajectory_continuation`). It cannot be retained and is not a performance mainline.

## Literature Anchors

This ranking follows the same broad direction as training-free or non-gradient agent improvement methods: learn external policies/reflections from trajectories, keep them interpretable, and validate them separately from the score that discovered failures.

- Reflexion stores verbal feedback in memory without updating model weights, supporting the idea of memory-mediated agent improvement rather than fine-tuning: https://huggingface.co/papers/2303.11366
- GEPA emphasizes reflective textual feedback over sparse reward-only optimization and argues that system trajectories plus natural-language reflection can be sample efficient: https://huggingface.co/papers/2507.19457
- BFCL V4 makes memory/tool behavior a first-class evaluation concern, which is why a memory-operation retain family is better aligned with the current benchmark than CTSPC file/path trajectory forcing.

## Gate Before Any Retain Claim

```text
theory_prior_pass = true
offline_negative_controls_pass = true
dry_run_compile_pass = true
runtime_adapter_ready = true
dev_scorer_positive = true
holdout_non_regress_or_positive = true
retain = allowed only after holdout
```

Current state stops at offline dry-run/simulation. It is a retain candidate, not a retained rule.
