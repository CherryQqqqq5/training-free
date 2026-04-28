# Memory First-Pass Dev Smoke Readiness

This document explains why the project does not yet have a retained rule or BFCL +3pp evidence, and what must be true before a memory-only smoke run can be requested.

## Current Decision

Verdict: runtime adapter readiness is now offline-ready, but BFCL smoke still requires a separate explicit approval and frozen smoke protocol.

The best retain candidate is `memory_first_pass_retrieve_soft_v1`. It now has both a dry-run policy unit and a runtime-compatible adapter rule for future smoke testing.

## Engineering Blocker Resolved

The BFCL patch runner starts GRC with a `rules-dir`. The runtime engine loads YAML files containing `rules` or single `Rule` documents. It explicitly skips YAML files whose top-level key is `policy_units`, because those are selector/compiler metadata.

Current memory policy artifact:

```text
outputs/artifacts/phase2/memory_operation_obligation_dry_run_v1/first_pass/policy_unit.yaml
```

This artifact is intentionally:

```text
runtime_enabled = false
exact_tool_choice = false
argument_creation_count = 0
candidate_commands = []
planned_commands = []
```

Therefore, if BFCL is run directly against this dry-run artifact, the memory policy will not be evaluated. Any score delta would be uninterpretable.

## New Readiness Check

The repository now has a fail-closed checker:

```bash
PYTHONPATH=.:src .venv/bin/python scripts/check_memory_operation_runtime_smoke_readiness.py --compact
```

Current expected output after the runtime adapter compile step:

```text
memory_runtime_adapter_ready = true
memory_dev_smoke_ready = true
loaded_memory_runtime_rule_count = 1
next_required_action = request_separate_memory_only_dev_smoke_approval
```

This still does not authorize BFCL execution. It only proves a future smoke would exercise a runtime-loadable adapter rather than a metadata-only `policy_unit.yaml`.

## Smoke Preconditions

A future memory-only dev smoke request requires all of the following:

```text
provider = novacode / 创智
runtime adapter exists and is loadable by RuleEngine
loaded memory runtime rule count > 0
dry-run boundary check passed
activation simulation passed
negative-control activation count = 0
argument creation count = 0
exact tool choice = false
no destructive memory tools
no raw trace/case/scorer/gold/support-hash text in runtime artifact
fixed memory-only case list
baseline and candidate commands preregistered
```

## Smoke Scope

If the above gates pass, the only acceptable first experiment is a small memory-only dev smoke. It must ask:

```text
Does the frozen memory_first_pass policy reduce prose-only answers in no-witness memory retrieval cases without creating arguments, forcing tools, or invoking destructive memory operations?
```

It must not claim +3pp, SOTA, retain, holdout generalization, or full BFCL performance.

## Non-Authorization

This document does not authorize:

- BFCL/model/scorer execution.
- Holdout scorer.
- 100-case or full BFCL.
- Retained memory claims.
- Huawei +3pp claims.

## First Smoke Attempt Status

A 3-case `memory_kv` baseline attempt was started with `novacode` after the protocol was approved. The run was stopped before candidate execution because BFCL emitted missing `memory_snapshot/customer_final.json` warnings and started each attempted case from empty memory. The observed baseline accuracy was `0.0`, so the run is not attributable to `memory_first_pass_retrieve_soft_v1` and is not algorithm evidence.

Recorded compact blocker:

```text
outputs/artifacts/phase2/memory_operation_dev_smoke_v1/memory_operation_dev_smoke_attempt_blocker.json
```

Next required action is to audit BFCL memory subset snapshot initialization before any candidate smoke run.
