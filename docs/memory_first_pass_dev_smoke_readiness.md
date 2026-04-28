# Memory First-Pass Dev Smoke Readiness

This document explains why the project does not yet have a retained rule or BFCL +3pp evidence, and what must be true before a memory-only smoke run can be requested.

## Current Decision

Verdict: `REQUEST CHANGES` before smoke BFCL.

The best retain candidate is `memory_first_pass_retrieve_soft_v1`, but it is currently a dry-run policy unit. It is not a runtime rule loaded by the BFCL candidate runner.

## Engineering Blocker

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

Current expected output is fail-closed:

```text
memory_runtime_adapter_ready = false
memory_dev_smoke_ready = false
first_failure = runtime_rule_yaml_present
next_required_action = implement_runtime_rule_adapter_before_memory_dev_smoke
```

This is the correct state. It prevents a BFCL run that would not exercise the proposed memory policy.

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
