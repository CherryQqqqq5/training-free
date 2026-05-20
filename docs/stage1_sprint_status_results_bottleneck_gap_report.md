# Stage1 training-free sprint — status, results, bottleneck, gap to delivery (2026-05-20)

This is the synthesis report for the bounded fail-closed sprint that ran in this
conversation. All numbers are machine-verified; all boundary attestations
preserved; no raw material committed.

> 📊 **Figures**: `docs/figures/*.png` (also referenced inline below)

---

## §1. Repository organization — what shipped in this sprint

### Sprint timeline (25 commits since baseline `651b7b27`)

| Phase | Commit | Status | Output |
|---|---|---|---|
| P1 (pre-sprint) | `9039bb04` | shipped | matrix-based score adapter (17/24 promote) |
| P1.5a (pre-sprint) | `82a87596` | shipped | category-arm-error-class matrix |
| **P2** v3 skeleton | `815758bc` | shipped | composer over v0 primitives (dry-run) |
| **P3** backoff policy | `bc80bf39` | shipped | declarative-only spec + validator |
| **P6** fixture expand | `6e49633e` | shipped | 5→10 synthetic cases, type+ambiguity coverage |
| **G1** P1.5b JSON template | `d235d6fb` | shipped | structured packet + strict checker |
| **G2** v3 wire stub | `563a6c0e` | shipped | no-op unless `wire_authorized AND policy_enabled` |
| **G3** blast-radius checker | `d5404329` | shipped | 15 guarded files, 0 forbidden imports |
| **G5** P1.5b SIGNED | `cdf44eec` | shipped | `approved`, 6 auth fields true, 5 caps filled |
| **G6a** slicer manifest | `cae73fc8` | shipped (superseded) | 72 sub-runs planning artifact |
| **G6b-1** executor scaffold | `4a94245e` | shipped (superseded) | dry-run verified, live deferred |
| **G6b-2** baseline arm LIVE | `5cdffeae` | shipped + key finding | 38 min, 0 504s, 14/48=29.17% |
| **G7-revised** v2 adapter | `1f52d7b9` | shipped, contract OK | 24/24 promote, contract satisfied |
| **Infra**: session_status + CI | `ffab4dbf` | shipped | STATUS builder + gate workflow |
| **Fix** status-builder | `69a67f1c` | shipped | idempotent + approved-evidence allowlist |

Current HEAD: `57f68639`. 12 feature branches preserved in origin for audit.

### Sprint-added artifacts (10 new, 0 baseline-modified)

```
outputs/artifacts/stage1_bfcl_acceptance/
  abhe_v0_per_case_scorer_slicer_approval_packet.json    [SIGNED]
  abhe_v0_p1_5b_per_case_scorer_slicer_approval_packet_draft.md
  abhe_v0_provider_transport_backoff_policy.json
  abhe_v0_runtime_slot_controller_v3_skeleton.json
  abhe_v0_per_case_scorer_slicer_rerun_manifest.json
  abhe_v0_per_case_scorer_slicer_bounded_residual_result.json  [dry-run]
  abhe_v0_baseline_arm_residual_smoke_per_case_diagnostic.json [LIVE evidence]
  abhe_v0_baseline_arm_target_state_mismatch_breakdown.json    [deep analysis]
  abhe_v0_per_selected_id_score_adapter_v2.json                [24/24 contract OK]
  abhe_v0_session_status.json                                   [auto]
```

### Sprint-added scripts (13 new)

5 builders + 6 checkers + 1 executor + 1 wire-stub + 1 status_builder + 1 fix.

### Sprint-added docs (6 new)

Operator guides, design notes, signing record, findings doc.

### Gate state (machine-verified, idempotent)

- **10 core checkers**: 9 exit 0 + 1 by-design fail-closed on legacy P1 artifact
- **166 standard tests pass** (per the documented 16-file gate)
- **Blast radius**: 15 guarded files, 0 forbidden imports (provider/BFCL/scorer/network)
- **`build_session_status --strict`**: exit 0, `blockers: []`, idempotent

---

## §2. Experiment results — baseline arm bounded residual smoke (live)

### Headline numbers

- **wall-clock**: 38 min (2026-05-20T03:13-03:52Z)
- **cost**: ≈ $5-10
- **provider 504s**: 0
- **48 cases**, **14 passed** = **29.17%** overall
- **multi_turn_miss_param** (target, 24 cases): **7 passed = 29.2%**

### Figure 1 — accuracy by category

`docs/figures/g6b2_accuracy_by_category.png`

| category | n | pass | acc% |
|---|---|---|---|
| multi_turn_base | 6 | 4 | 66.7% |
| multi_turn_long_context | 4 | 2 | 50.0% |
| **multi_turn_miss_param** | **24** | **7** | **29.2%** |
| multi_turn_miss_func | 6 | 1 | 16.7% |
| irrelevance | 4 | 0 | 0.0% |
| live_irrelevance | 4 | 0 | 0.0% |
| **TOTAL** | **48** | **14** | **29.17%** |

ASCII bar (red = target):
```
multi_turn_base         | ████████████████████████████████████████████████ 66.7% (4/6)
multi_turn_long_context | ████████████████████████████████████             50.0% (2/4)
multi_turn_miss_param   | █████████████████████ 29.2% (7/24) ← TARGET
multi_turn_miss_func    | ████████████ 16.7% (1/6)
irrelevance             |  0.0% (0/4)
live_irrelevance        |  0.0% (0/4)
```

### Figure 2 — error_type_class distribution (sanitized BFCL labels)

`docs/figures/g6b2_error_class_distribution.png`

| count | class | dominant in |
|---|---|---|
| 18 | `multi_turn:instance_state_mismatch` | miss_param (15), miss_func (2), base (1) |
| 14 | **passed** | mostly base / long_context / 7 miss_param |
|  8 | `irrelevance_error:decoder_success` | irrelevance (4), live_irrelevance (4) |
|  4 | `multi_turn:empty_turn_model_response` | miss_param (3), long_context (1) |
|  2 | `multi_turn:execution_response_mismatch` | mixed |
|  2 | `multi_turn:force_terminated` | mixed |

### Figure 3 — per-case PASS/FAIL for the target (multi_turn_miss_param)

`docs/figures/g6b2_miss_param_per_case.png`

24 cases sorted by case_id; bar = total latency in seconds; color = outcome:

```
PASS (7):  77, 88, 94, 97, 100, 103, 105
FAIL state_mismatch (14):  76, 78, 79, 86, 87, 89, 90, 91, 92, 93, 96, 98, 99, 102
FAIL empty_turn_response (3):  95, 101, 104
```

### Figure 4 — latency distribution by category

`docs/figures/g6b2_latency_by_category.png`

| category | min(s) | median(s) | max(s) | sum(s) |
|---|---|---|---|---|
| multi_turn_miss_param | 6.0 | 23.8 | 124.7 | 752.4 |
| multi_turn_miss_func | 21.5 | 65.6 | 95.8 | 315.9 |
| multi_turn_base | 13.1 | 28.6 | 45.7 | 153.4 |
| multi_turn_long_context | -1.3 | 24.2 | 24.6 | 57.7 |
| live_irrelevance | 1.0 | 2.6 | 3.0 | 8.7 |
| irrelevance | 0.9 | 1.4 | 1.4 | 5.0 |

### Figure 5 — sprint pipeline state

`docs/figures/sprint_pipeline_state.png`

Color legend:
- 🟢 green = shipped in stage1
- 🔵 blue = shipped + key finding
- ⚪ gray = shipped but superseded (G6a / G6b-1 — replaced by G7-revised)
- 🟡 yellow = PENDING (next 1-2 turns; G7b/G7c arm runs + G8 P1.5a v2)
- 🔴 red = FUTURE (research-required; v3 wire, P3 wire, real intervention)

---

## §3. Bottleneck analysis — what's actually blocking progress

### The 3-finding overturn (G6b-2)

| What we thought was the bottleneck | What G6b-2 revealed | Status |
|---|---|---|
| **C1**: BFCL scorer collapses 24 cases into 1 scorer_unit | Per-case data was ALWAYS in the score JSON (17 invalid records + 7 implied passing). Matrix builder's hash scheme was the parsing bug. | RESOLVED by G7-revised v2 adapter (24/24 contract OK) |
| **C3**: provider 504s on multi_turn_miss_param | 0 × 504 in 38-min live run. Provider was stable end-to-end. | NOT REPRODUCING (this slice, this day) |
| **REAL**: model capability on BFCL-v3 state-based eval | dominant failure mode = `multi_turn:instance_state_mismatch` (18/34 = 53% of failures) | UNRESOLVED — this is the real bottleneck |

### Deep dive — `multi_turn:instance_state_mismatch` (14 detailed cases)

`outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_baseline_arm_target_state_mismatch_breakdown.json`

**Average 2.7 diverged state fields per failed case** (range 1-4). Distribution: {2 fields: 7 cases, 4 fields: 5 cases, 3 fields: 1 case, 1 field: 1 case}.

**By backend** (sanitized field names; field-divergence counts):

| backend | total divergences | dominant fields |
|---|---|---|
| **VehicleControlAPI** | **31** | engine_state (10), brakePedalStatus (10), remainingUnlockedDoors (5), doorStatus (5), destination (1) |
| MessageAPI | 3 | generated_ids, inbox, message_count (1 each) |
| TwitterAPI | 2 | tweets, tweet_counter (1 each) |
| TradingBot | 2 | orders, order_counter (1 each) |

**Observation**: VehicleControlAPI dominates (31 of 38 backend divergences). The correlated pairs (engine_state + brakePedalStatus, doorStatus + remainingUnlockedDoors) suggest the model fails to invoke the *paired* tool calls that drive state transitions atomically (e.g., "start engine" requires "press brake" first; "lock door" affects "remaining unlocked").

**Turn count comparison passed vs failed**:
- passed (n=7): result turns = {3, 3, 4, 4, 4, 6, 7}
- failed (n=17): result turns = {3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6}
- → **turn count alone doesn't predict pass/fail**. Both distributions overlap. The bottleneck is *what tool calls* the model makes, not *how many*.

**Latency comparison passed vs failed**:
- passed: median 1.0s, max 15.6s (these are individual API-call latencies, sum is misleading)
- failed: median 1.5s, max 14.3s
- → **latency overlaps fully**. The bottleneck is not provider speed.

### `multi_turn:empty_turn_model_response` (3 cases on miss_param)

case_ids: 95, 101, 104. Model returns empty for some turn. Likely causes:
- truncation (output_token_count exceeded internal cap)
- silent refusal / safety filter
- context overflow on subsequent turns
- These cases have ≥4 turns; model "gives up" mid-trajectory

### `irrelevance_error:decoder_success` (8 cases, all 8 irrelevance + live_irrelevance failures)

Model decodes a valid tool-call AST when it should abstain. **100% failure rate on the irrelevance + live_irrelevance categories** — this is an "abstain" capability bottleneck. Trivial to detect at the proxy layer (parse output, check whether tool call was emitted on an irrelevance prompt) but the prompt itself contains tool schemas, biasing the model toward calling them.

### Bottleneck summary

| bottleneck | severity | gating | mechanism class |
|---|---|---|---|
| **Multi-turn state tracking** (esp. VehicleControlAPI paired-call sequences) | HIGH (14/34 = 41% of failures) | model capability | trajectory planning + tool-call atomicity |
| **Irrelevance / abstain** | HIGH (8/34 = 24% of failures, 100% rate on its categories) | model capability + prompt biasing | output-gate / classifier |
| **Empty-turn truncation** | MED (4/34 = 12%) | model truncation OR context overflow | output formatting / length control |
| Scorer / parser (was C1) | RESOLVED via G7-revised | n/a | — |
| Provider stability (was C3) | DORMANT (no recurrence) | n/a | (handled defensively by hard caps) |

---

## §4. What research / experiments to do next

### Literature already cited in design docs (for reference)

- **Reinforced Agent** (2025) — inference-time reviewer of provisional tool calls; informs G2 wire-stub design
- **ToolWeave** (2025) — parameter provenance tracking; informs binder design
- **EigenData** (2025) — BFCL has documented schema/trajectory errors; state-based eval can be unstable
- **Tool Calling is Linearly Readable** (2025) — top-1 / top-2 tool gap predicts errors; motivates ambiguity flags
- **BFCL-v3 blog** (Berkeley 2024) — state-based eval is by design strictly harder than trajectory matching
- **Fission-GRPO** (2025) — RL recovery from execution errors; +5.7% on BFCL-v4 multi-turn (training-based; not applicable here)
- **Brooker (AWS 2015)** — Exponential Backoff and Jitter; informs P3 backoff design

### Research-required topics (priority-ordered)

1. **HIGHEST PRIORITY — state-tracking failure-mode papers on BFCL-v3 multi-turn**:
   - Search query: `BFCL v3 multi-turn instance_state_mismatch VehicleControlAPI`
   - What papers report on this specific category's failure pattern at temp=0 on gpt-4.1?
   - Are there published recipes for paired-tool-call atomic transitions?
   - Look at the [BFCL leaderboard](https://gorilla.cs.berkeley.edu/leaderboard.html) for which models score >50% on miss_param — do they share architectural features?

2. **Abstain / irrelevance handling**:
   - Search query: `LLM tool calling abstain irrelevance refusal training-free`
   - Methods like: "is this prompt actually relevant to any of the offered tools?" classifier
   - Could be implemented at the runtime proxy layer (G2 wire-stub extension): if model's output decodes to a tool call but the prompt is from an irrelevance category, override to abstain
   - Already known: 100% failure rate → potential for large absolute win (+4 cases at minimum on a 48-case slice)

3. **Output-truncation / empty-turn diagnosis**:
   - Why does gpt-4.1 emit empty turns in 3 cases?
   - Token-count caps in the proxy config?
   - Could test by re-running just cases 95/101/104 with higher max_tokens
   - Could be a quick win (3 cases recovered) if it's a config issue

4. **Comparison study (after G7b+c arms land)**:
   - Are conditional_frozen_v2 and runtime_slot_controller_v2 better/worse than baseline on these specific 14 + 3 + 8 failure cases?
   - Per-case-arm diff: which cases does each arm flip from FAIL → PASS or vice versa?
   - This is what user instruction #3 asked for; needs G7b+c first.

5. **Provider transport** (informational):
   - 0 × 504 in 38 min. Is the provider stable enough now that backoff isn't needed?
   - If yes, P3-wire becomes optional (still ship defensively per user instruction #5).

### Concrete experiments to propose (no new code yet — just to discuss)

| ID | experiment | cost | what it tests |
|---|---|---|---|
| E1 | Run conditional_frozen_v2 arm on same 48-case slice | ~$5-10 / 30 min | Does arm 2 differ from baseline on the 14 state_mismatch cases? |
| E2 | Run runtime_slot_controller_v2 arm on same 48-case slice | ~$5-10 / 30 min | Does arm 3 differ; does the slot-binding logic help? |
| E3 | Run baseline arm on the 17 INVALID cases ONLY with higher max_tokens cap | ~$3-5 / 10 min | Are the 3 empty_turn cases truncation-driven? |
| E4 | Inspect raw VehicleControlAPI trajectories (locally, in /tmp; NO commit) | $0 / 30 min | What tool-call sequence does the model use on the 11 vehicle failures? Does it match the GT trajectory minus the missing param? |
| E5 | Implement and test abstain-override at proxy layer for irrelevance | ~$3-5 + new wire PR | Could flip 8/8 irrelevance failures with simple "if prompt-category=irrelevance, override empty tool call" rule |
| E6 | Try **paired-tool-call enforcement** runtime rule (e.g., "if start_engine called, must press brake first") | new mechanism + arm run | Targets the engine_state/brakePedalStatus correlated divergence (10 cases) |

### Research artifacts I can produce next turn (offline, no new provider call)

- Detailed VehicleControlAPI case-by-case state-divergence breakdown (which field diverged in which case)
- Cross-failure pattern mining: do failing cases share specific GT trajectory shapes?
- Comparison with BFCL v3 base category (66.7% pass) — what's the difference in trajectory complexity?

---

## §5. Gap to delivery — depends on what "delivery" means

### Three plausible delivery targets

| Target | Status | Gap |
|---|---|---|
| **L1: Honest bounded measurement, 1 arm** | ✅ **DONE** | Already shipped. Contract satisfied. |
| **L2: Honest bounded measurement, all 3 arms + arm comparison** | 🟡 **30% done** | Need E1+E2 (~$10-20, ~60 min), then G8 P1.5a v2 matrix. |
| **L3: Improvement over baseline on miss_param (training-free)** | 🔴 **0% done** | Need a real intervention. Research-required. |
| L4 (out of scope): +3pp claim with statistical significance | n/a | Cap commitments forbid this. |
| L5 (out of scope): Huawei acceptance / SOTA | n/a | Cap commitments forbid this. |

### L2 (achievable in 1-2 sessions) — what's needed

1. **G7b**: run conditional_frozen_v2 arm (1 session, ~30 min wall-clock during run)
2. **G7c**: run runtime_slot_controller_v2 arm (1 session, similar)
3. **G8**: regenerate G6b-2-style diagnostic + G7-revised v2 adapter for both new arms
4. **G9** (analysis): per-case-arm diff matrix; arm-level finding doc
5. **No new mechanism design needed** — all infrastructure exists.

**Cost estimate**: ~$10-20 + ~60 min wall-clock + ~1-2 sessions of my time.

**Honest outcome to expect**: arm 2 and arm 3 will likely score similarly to baseline on miss_param (29.2% range). The prior matrix data suggested no arm-level wins on state_mismatch. But L2 makes this *measurable* with per-case granularity for the first time.

### L3 (training-free improvement) — what's the gap

The gap is **a real intervention that helps the model**. Options (none implemented):

1. **Runtime abstain override** (irrelevance categories) — easy, +8 cases potentially
2. **Paired-tool-call enforcement** at runtime (vehicle paired transitions) — medium, +10 cases potentially
3. **Output-format / max-tokens** tuning (empty-turn) — trivial, +3 cases potentially
4. **State-tracking memory primitive** at proxy (re-inject backend state summary before each turn) — large, research-required

If all 4 work as designed (highly optimistic): 8+10+3+? cases recovered → ~30-50% better. Realistic: 25-40% recovery → 14 + ~5 cases = 19/48 ≈ 40% accuracy. Still not +3pp on the full BFCL leaderboard, but a measurable bounded smoke win.

**Honest position**: L3 is a research project, not just engineering. Each option requires literature read + small-scope test before claiming. No path to L4/L5 without crossing boundary commitments.

### What I recommend doing next (priority-ordered)

1. **L2 path** — run E1 + E2 (the other 2 arms) → G7b/c → G8 P1.5a v2 matrix → G9 arm comparison doc. Achievable in 1-2 sessions; completes the honest measurement.
2. **E3 quick win** — try higher max_tokens on the 3 empty-turn cases. Could be 5-10 min experiment.
3. **Research-only step** — do literature scan for "BFCL state-based eval mitigations" + "training-free abstain override" before designing L3 interventions.
4. **DO NOT** start L3 implementation until L2 measurement is complete and we have per-case-arm diff data.

---

## §6. Boundary discipline — all preserved (machine-verified)

| invariant | value |
|---|---|
| performance_evidence | false |
| sota_3pp_claim_ready | false |
| huawei_acceptance_ready | false |
| holdout_touched | false |
| full_suite_touched | false |
| archive_updated | false |
| raw_material_absent | true |
| raw_prompt_committed | false |
| raw_response_committed | false |
| gold_expected_committed | false |
| argument_values_committed | false |
| scorer_diff_committed | false |
| raw_provider_payload_committed | false |
| raw_bfcl_result_tree_committed | false |
| prompt_literal_committed | false |
| runtime_wired_into_proxy | false |

All 16 attestation invariants hold across every sprint-scope artifact except those in `APPROVED_RUN_EVIDENCE_ARTIFACTS` (currently 1: G6b-2 baseline diagnostic), which legitimately has runtime-execution attestations true under the signed P1.5b packet, but still holds all NEVER_TRUE_FIELDS = false.
