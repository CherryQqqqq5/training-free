# Memory Operation Dev Scorer Application Gate

This document is a gate proposal, not an authorization to run BFCL/model/scorer.

## Scope

The only candidate family covered here is:

```text
memory_first_pass_retrieve_soft_v1
```

It is compiled from the `memory_operation_obligation` theory prior:

```text
If the user has an observable retrieve-memory intent, memory tools are available, and no strong memory value witness exists, the agent should receive soft guidance to use memory retrieval/search/list capabilities before answering from prose.
```

The policy is training-free and does not change model weights.

## Current Offline Evidence

Required compact artifacts are present at HEAD `a0a41014`:

```text
memory_operation_candidate_count = 78
first_pass_compiler_allowlist_count = 48
weak_witness_compiler_input_count = 0
negative_control_audit_passed = true
memory_first_pass_dry_run_policy_unit_count = 1
memory_tool_family_resolver_audit_passed = true
memory_activation_simulation_passed = true
activation_count = 48
negative_control_activation_count = 0
argument_creation_count = 0
runtime_enabled = false
exact_tool_choice = false
candidate_commands = []
planned_commands = []
```

This proves an offline self-evolution workflow, not benchmark performance.

## Non-Authorization

This document does not authorize:

- BFCL scorer execution.
- Holdout scorer execution.
- 100-case or full BFCL.
- M2.8 formal performance evaluation.
- Runtime enablement by default.
- Retained memory claims.

Any scorer execution requires a separate explicit approval.

## Preconditions Before Any Dev Scorer Request

A future memory-only dev scorer request must first verify:

```text
artifact_boundary_for_committed_outputs = pass
memory_operation_negative_control_audit_passed = true
memory_operation_compiler_allowlist_ready = true
memory_dry_run_policy_ready = true
memory_resolver_audit_passed = true
memory_activation_simulation_passed = true
runtime_enabled = false in committed artifacts
exact_tool_choice = false
argument_creation_count = 0
weak_lookup_witness_activation_count = 0
```

The scorer plan must also state:

```text
provider = novacode / 创智
openrouter = not used
candidate family = memory_first_pass_retrieve_soft_v1 only
CTSPC-v0 = disabled
old repair stack = disabled
holdout = not touched
```

## Required Dev Scorer Stop-Loss Metrics

The first scorer, if separately approved, should be a memory-only dev check. It should stop after one paired baseline/candidate run and should not expand to holdout unless the formal gate passes.

Stop-loss:

```text
candidate_accuracy >= baseline_accuracy
case_regressed_count <= 1
net_case_gain >= 0
non_memory_control_regression_count = 0
memory_negative_control_false_positive_count = 0
```

Formal dev gate:

```text
candidate_accuracy > baseline_accuracy
case_fixed_count > case_regressed_count
net_case_gain >= 2
memory_policy_activated_count > 0
memory_policy_activation_precision >= 0.8
argument_creation_count = 0
exact_tool_choice_coverage = 0.0
stop_allowed_false_positive_count = 0
case_report_trace_mapping = prompt_user_prefix
```

## Mismatch Diagnostics If Dev Fails

If dev scorer fails, do not patch case ids or tool signatures. Produce a mismatch report with:

```text
policy_not_activated
resolver_empty
model_ignored_guidance
memory_tool_called_but_no_value_returned
memory_value_returned_but_trajectory_failed
negative_control_false_positive
non_memory_regression
```

Then decide whether the issue is:

```text
policy prior too broad
resolver semantics wrong
runtime prompt serialization weak
BFCL memory task requires second-pass observed-key policy
benchmark variance / non-action regression
```

No retain decision can be made from dev alone. Retain remains impossible without holdout evidence.
