# Training-Free ABHE-v0

> **One-liner**: Fail-closed training-free self-evolution loop for BFCL function-calling improvements.

> ⚠ **Evidence boundary** — at any prompt that touches results: `performance_evidence=false`, `holdout_touched=false`, `full_suite_touched=false`, `archive_updated=false`. **NO** +3pp / SOTA / Huawei-acceptance claims allowed.

## Goal

Without training model weights, gradually improve BFCL function-calling performance via:
behavior archive → candidate mechanism generation → fresh BFCL dev slice → trace audit → archive state transition.

Success = stable per-case/per-turn scorer evidence + missing-param runtime controller + full BFCL paired run approved.

## Tech Stack
- Language: Python (venv at `.venv/`)
- Domain: LLM tool-calling / BFCL benchmark
- Key concept: ABHE = Archive-Backed Hypothesis Evolution (fail-closed)
- Hardware: server `10.220.5.159` (root@qiuyn0-0)

## Current Status

**Phase**: bounded dev / diagnostic. **Not** in full BFCL or Huawei acceptance.

Branch (live snapshot on remote): `cleanup/repo-tidy-pre-p1` @ `e0a6e87`
*(user-cited intended branch: `stage1-bfcl-performance-sprint` @ `badc821` — verify before any acceptance-grade run)*

Closed-loop is running; positive signals on bounded dev:
- `state_tracking_v0`: 0.5 → 0.8 (20-case smoke)
- `hallucination_abstain_v0`: 0.3 → 1.0 (20-case) / 0.333 → 1.0 (expanded)
- `frozen_v2`: baseline 30/54 → **46/54** on fresh balanced slice

But the **real bottleneck** is not "model unaware to ask for missing params" — it's **lack of an executable slot-state / tool-call controller**. Trace audit shows `runtime_slot_controller_v2` marker appears but `slot_bind_repair_count = 0`, `target_bucket_reduction = 0`.

## Active Lines of Work

- [ ] Per-selected-id / per-turn scorer alignment (current results are scorer-unit / category-level, not strict case-level)
- [ ] Reduced batch rerun for runner/scorer stability (not full BFCL yet)
- [ ] Rewrite missing-param mechanism from prompt-guidance to runtime-level controller:
  - `required_arg_schema_reader_v0`
  - `valid_tool_call_guard_v0`
  - `prior_tool_observation_slot_binder_v0`
  - `prerequisite_lookup_planner_v0`
- [ ] Keep regression suite alive (no-tool boundary, live_relevance, multi_turn_base must not regress)
- [ ] After stable reduced + distinct residual slice → broader dev → approved full BFCL paired run

## Key Files / Entry Points

```
abhe_archive/                                    behavior archive + opportunity table + transitions
configs/runtime_bfcl_structured.yaml             runtime config
scripts/check_abhe_*.py                          gate/checker scripts (no_leakage, review_bundle, approval_chain, planning_ready)
scripts/build_* / run_* / plan_*                 builder / runner / transition planner
outputs/artifacts/stage1_bfcl_acceptance/        compact evidence area (the important one)
  ├── active_evidence_index.json
  ├── abhe_review_bundle.json
  ├── abhe_planning_ready.json
  └── abhe_approval_chain.json
tests/                                           gate / checker / regression tests
```

## Known Gotchas

- **Two SSH configs share IP `10.220.5.159`** (ports 31256 and 30412). The active session used port 30412 → user=root, host=qiuyn0-0.
- `runtime_slot_controller_v2` mechanism is **mounted but inert** — trace shows zero bind repairs. Don't promote it yet.
- `long_context_state_retrieval_v0` causes non-target regressions → narrow router / pause mainline.
- `missing_param_epistemic_gate_v0` has no independent scorer signal → don't promote.
- Mismatch between user-stated branch and remote-active branch → always `git status` before drawing conclusions.

## Quick Commands

```bash
# enter project
ssh -t 10.220.5.159 'cd /cephfs/qiuyn/training-free && exec $SHELL -l'

# state checks
git status --short
git rev-parse HEAD
git ls-remote origin stage1-bfcl-performance-sprint

# ABHE checker chain (compact + strict)
PYTHONPATH=.:src .venv/bin/python scripts/check_abhe_no_leakage_boundary.py --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_abhe_review_bundle.py     --write --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_abhe_approval_chain.py    --write --compact --strict
PYTHONPATH=.:src .venv/bin/python scripts/check_abhe_planning_ready.py    --write --compact --strict
```

## Distance-to-Delivery (snapshot)

Close: bounded-dev positive signal + presentable technical line.
Still missing for +3pp formal delivery:
1. true per-case/per-turn scorer evidence
2. stable reduced rerun
3. missing-param runtime controller breakthrough
4. broader dev slice validation
5. approved full BFCL paired run
6. all of: no-regression / no-leakage / no-holdout-violation passing

## Links
- DECISIONS.md — boundary rules + rejected approaches
- ENVIRONMENT.md — venv, PYTHONPATH, server access
- NEXT_STEPS.md — concrete next actions (live)
- memory/ — distilled session notes
- GitHub: https://github.com/CherryQqqqq5/training-free
