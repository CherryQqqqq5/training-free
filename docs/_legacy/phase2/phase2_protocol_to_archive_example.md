# Phase-2 Example: Protocol -> Evaluation -> Trace -> Attribution -> Compile -> Patch -> Selection -> Archive

This is one concrete, reproducible example that matches the current Phase-2 `actionable no-tool decision` logic.

## Source Boundary

I did **not** find the named raw dataset files

- `BFCL_v3_multi_turn_miss_param.json`
- `multi_turn_func_doc/*.json`

in the local repo, mounted server repo, or `/cephfs/qiuyn` tree at the time of writing.

So this example uses the next-best real sources that are already present in the workspace:

- the original BFCL request/response trace:
  - `/Users/cherry/mnt/training-free/outputs/phase1_checks/multi_turn_miss_param/traces/000eedd4-9653-4913-b93a-f9c1a9d3af95.json`
- the mined Phase-2 failure entry:
  - `/Users/cherry/mnt/training-free/outputs/phase2_targeted_v2/failures.jsonl`
- the historical compiled candidate summary:
  - `/Users/cherry/mnt/training-free/outputs/phase2_targeted_v2/compile_status.json`
- the current compiler output on this single failure, regenerated from the current codebase during this note

This keeps the example factual and reproducible.

## 1. Protocol

### Selected sample

- `trace_id = 000eedd4-9653-4913-b93a-f9c1a9d3af95`
- Why this one:
  - it has `tools_available`
  - it has `prior_explicit_literals_present`
  - it has `prior_tool_outputs_present`
  - it ends with a no-tool natural-language completion after a successful tool result
  - this is exactly the failure family the current Phase-2 patch line is trying to control

### Relevant tool docs embedded in the trace

From `request_original.tools`, the relevant Gorilla file-system tools are:

- `find(path=".", name="...")`
  - searches recursively and returns `matches`
- `cat(file_name="...")`
  - returns `file_content`
- `mkdir(dir_name="...")`
  - creates a directory in the current directory

### Relevant protocol tail from `request_original.input`

The immediately preceding interaction before failure was:

1. `find(path=".", name="goal")`
2. tool output: `{"matches":["./goals.txt"]}`
3. assistant prose summary describing that match
4. user: `For clarity, output the complete content of the first file you find on the terminal.`
5. `cat(file_name="goals.txt")`
6. tool output: `{"file_content":"Research topic selection Literature review Data collection Data analysis Draft writing Final submission"}`

This is already enough local evidence to continue structurally. The agent does not need to ask for more context.

## 2. Evaluation

### Slice-level baseline

From:

- `/Users/cherry/mnt/training-free/outputs/phase1_checks/multi_turn_miss_param/artifacts/metrics.json`
- `/Users/cherry/mnt/training-free/outputs/phase1_checks/multi_turn_miss_param/artifacts/failure_summary.json`

the verified baseline for `multi_turn_miss_param` was:

- accuracy: `36.5`
- correct count: `73 / 200`
- dominant validation failure:
  - `empty_tool_call = 807`

This matters because the selected sample was one instance of that dominant no-tool failure regime.

## 3. Trace

### What the raw model did

In the selected trace, after `cat(file_name="goals.txt")` returned successfully, the raw assistant response was:

> I've displayed the complete content of the file "goals.txt" from the "academic_venture" directory...

Trace facts:

- `request_endpoint = /v1/responses`
- `raw_finish_reason = "stop"`
- `raw_tool_calls = false`
- `final_message.tool_calls = []`

### How the runtime recorded it at Phase-1

In the original Phase-1 trace, this was still classified as:

- `empty_tool_call`

with:

- `message = "no tool call emitted for tool-enabled request"`

That is historically accurate for the older taxonomy.

## 4. Attribution

The same trace was later re-mined into Phase-2 as:

```json
{
  "trace_id": "000eedd4-9653-4913-b93a-f9c1a9d3af95",
  "error_type": "actionable_no_tool_decision",
  "request_predicates": [
    "tools_available",
    "prior_explicit_literals_present",
    "prior_tool_outputs_present"
  ],
  "request_literals": ["reference_goals.txt", "goals.txt"]
}
```

This is the critical attribution step.

The failure is not just “the model returned no tool call.” It is:

- tools were available
- local file identity was already explicit (`goals.txt`)
- a fresh tool result was present (`file_content`)
- the assistant still switched into prose-only completion

That is exactly the Phase-2 interpretation of an actionable no-tool continuation failure.

## 5. Compile

I regenerated a patch from **just this one failure** using the current compiler.

Compile result:

- `status = actionable_patch`
- `source_failure_count = 1`
- `failure_ir_count = 1`
- `rule_count = 1`
- `actionable_rule_count = 1`

The generated rule is policy-first:

- `rule_id = rule_global_no_tool_actionable_no_tool_decision_prior_explicit_literals_present_prior_tool_outputs_present_tools_available_v1`
- `scope.patch_sites = ["prompt_injector", "policy_executor"]`

That is the current architecture line, not the older `verification_hook + fallback_router` line.

## 6. Patch

The generated `decision_policy` for this one-sample patch is:

- `request_predicates`
  - `prior_explicit_literals_present`
  - `prior_tool_outputs_present`
  - `tools_available`
- `continue_condition`
  - `tools remain available and locally grounded evidence supports another tool action`
- `stop_condition`
  - `do not stop with prose-only narration while the matched local continuation evidence still holds`
- `forbidden_terminations`
  - `prose_only_no_tool_termination`
- `evidence_requirements`
  - `prior_explicit_literals_present`
  - `prior_tool_outputs_present`
  - `tools_available`

The generated prompt fragments are also aligned with the same logic:

- emit the next tool call instead of prose-only completion
- reuse explicit literals already present in context
- ground the next action in prior tool outputs

## 7. Selection

This single sample is not enough by itself. Selection still has to happen at run level.

From the documented verified history in `/Users/cherry/mnt/training-free/docs/progress_2026-04-21.md`:

| Run | Slice | Accuracy | Correct Count | Interpretation |
| --- | --- | ---: | ---: | --- |
| baseline | `multi_turn_miss_param` | `36.5` | `73 / 200` | compatibility baseline |
| `primary_v2` | `multi_turn_miss_param` | `0.0` | `0 / 200` | rejected; over-broad continuation forcing |
| `primary_v3` | `multi_turn_miss_param` | `35.0` | `70 / 200` | recovered from catastrophic regression, but still below baseline |
| `primary_v4` | `multi_turn_miss_param` | `40.0` | `80 / 200` | first clear positive targeted uplift |
| `rerun_v4` | `multi_turn_miss_param` | `43.5` | `87 / 200` | strongest verified target-slice evidence |

The selected sample above is representative of the failure family that was narrowed and then partially converted into uplift across `primary_v4` and `rerun_v4`.

## 8. Archive

This example is now archived in two places:

1. This focused walkthrough:
   - `/Users/cherry/.codex/worktrees/3253/training-free/docs/phase2_protocol_to_archive_example.md`
2. The running experiment ledger:
   - `/Users/cherry/mnt/training-free/docs/progress_2026-04-21.md`

## Short Read

If I had to explain the entire Phase-2 loop in one paragraph using one real sample, it would be:

> In trace `000eedd4-9653-4913-b93a-f9c1a9d3af95`, the model had already found `goals.txt` and successfully read its contents, but then answered in prose instead of continuing structurally. Phase-1 recorded this as a generic `empty_tool_call`; Phase-2 re-attributed it as an `actionable_no_tool_decision` because the next-step evidence was already locally present. The current compiler turns that failure into a policy-first rule with explicit request predicates, continuation/stop semantics, and forbidden termination. That failure family then became one of the main targets of the patch line that moved `multi_turn_miss_param` from `36.5` to `40.0`, and then to `43.5` on rerun.
