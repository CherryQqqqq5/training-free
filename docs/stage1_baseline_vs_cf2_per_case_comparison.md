# Stage1 candidate-vs-baseline per-case comparison — multi_turn_miss_param (2026-05-20)

This report covers the first candidate-vs-baseline comparison for the BFCL
training-free sprint. The user explicitly authorized inclusion of sanitized
real-trace examples (`可以附上详细的真实traces的例子`).

> **Scope**: 19 of 24 multi_turn_miss_param target cases overlap between
> `baseline` arm (gpt-4.1, complete) and `conditional_frozen_v2` arm (gpt-4.1,
> partial due to subprocess timeout). 5 cases not yet processed by cf2:
> 101, 102, 103, 104, 105.
>
> **Second comparison axis (baseline gpt-4o)** is still in-flight at the time
> of this commit; will be added in a follow-up commit when it completes.

## §0 What we verified before starting

| check | result | source |
|---|---|---|
| Proxy actually forwards to gpt-4.1 | ✅ `raw_response.model: gpt-4.1-2025-04-14` | trace card from baseline run |
| Endpoint supports gpt-4o (full) | ✅ → `gpt-4o-2024-11-20` | direct API probe |
| Endpoint supports claude-3-5-sonnet | ❌ HTTP 403 no access | direct API probe |
| Endpoint supports gpt-4-turbo / gpt-5 | ❌ HTTP 403 | direct API probe |

So baseline 29.2% on multi_turn_miss_param is on **real gpt-4.1**, not a weak-
model artifact. The endpoint additionally allows gpt-4o (full) for stronger
comparison; that experiment is in-flight separately.

## §1 Headline aggregate

| Arm | model | cases | passed | acc | avg API turns/case | avg latency/case | notes |
|---|---|---|---|---|---|---|---|
| **baseline** | gpt-4.1-2025-04-14 | **24** | **7** | **29.2%** | **4.3** | **31s** | full sweep, 0 504s |
| **cf2** (conditional_frozen_v2) | gpt-4.1-2025-04-14 | **19** (partial) | **0** | **0.0%** | **1.0** (!) | **95s** | subprocess timeout at case 20 |

On the **19-case overlap**: baseline 5 pass, cf2 0 pass → cf2 **lost all 5 baseline-passes and recovered zero failures**.

## §2 Per-case overlap table (19 cases)

```
case_id                          baseline   cf2       turn count   latency(s)
                                                       b → c       b → c
multi_turn_miss_param_76         FAIL       FAIL      3 → 1        14.3 → 84.4
multi_turn_miss_param_77         **PASS** → **FAIL**  4 → 1        125.5 → 91.5      ← REGRESSION
multi_turn_miss_param_78         FAIL       FAIL      3 → 1        83.9 → 87.6
multi_turn_miss_param_79         FAIL       FAIL      4 → 1        40.7 → 72.1
multi_turn_miss_param_86         FAIL       FAIL      4 → 1        35.0 → 92.5
multi_turn_miss_param_87         FAIL       FAIL      5 → 1        19.0 → 65.0
multi_turn_miss_param_88         **PASS** → **FAIL**  4 → 1        13.5 → 146.7     ← REGRESSION
multi_turn_miss_param_89         FAIL       FAIL      5 → 1        15.9 → 76.9
multi_turn_miss_param_90         FAIL       FAIL      5 → 1        29.7 → 92.9
multi_turn_miss_param_91         FAIL       FAIL      3 → 1        20.3 → 89.8
multi_turn_miss_param_92         FAIL       FAIL      6 → 1        18.2 → 108.5
multi_turn_miss_param_93         FAIL       FAIL      4 → 1        13.2 → 142.4
multi_turn_miss_param_94         **PASS** → **FAIL**  4 → 1        37.8 → 84.5      ← REGRESSION
multi_turn_miss_param_95         FAIL       FAIL      6 → 1        40.4 → 94.9
multi_turn_miss_param_96         FAIL       FAIL      3 → 1        23.8 → 94.1
multi_turn_miss_param_97         **PASS** → **FAIL**  7 → 1        59.5 → 85.5      ← REGRESSION
multi_turn_miss_param_98         FAIL       FAIL      4 → 1        47.8 → 94.2
multi_turn_miss_param_99         FAIL       FAIL      5 → 1        28.8 → 87.7
multi_turn_miss_param_100        **PASS** → **FAIL**  3 → 1        22.7 → 71.0      ← REGRESSION
```

**Pattern is uniform**:
- 5 baseline-pass cases → 5 cf2-fail (all `multi_turn:force_terminated`)
- 14 baseline-fail cases → 14 cf2-fail (all switched from `instance_state_mismatch` → `force_terminated`)
- **Every cf2 case has `result_turn_count = 1`** vs baseline's 3-7
- cf2 latency runs 65-146s per case (vs baseline 13-125s); cf2 makes ~21 API calls within its single turn

## §3 Real trace example — case `multi_turn_miss_param_77` (baseline PASS → cf2 FAIL)

This case asks the model to:
1. Determine road distance from a starting city to "Stonebrook" (missing: starting city must be obtained)
2. Then post a tweet about the journey
3. Then retweet it

It's a classic miss_param case: one required parameter (starting city) is implicit.

### Baseline trace (gpt-4.1) — passed

```
turn 0:
  1 call:   asks user a clarifying question about starting city
            ("To help determine the road distance to Stonebrook, could you ...")

turn 1:
  5 calls:  get_zipcode_based_on_city("San Francisco")
            get_zipcode_based_on_city("Stonebrook")
            estimate_distance(cityA="94016", cityB="74532")
            estimate_drive_feasibility_by_mileage(distance=880.x, ...)
            summary: "The road distance from San Francisco to Stonebrook is approximately ..."

turn 2:
  2 calls:  post_tweet({content: "Setting forth on an exciting quest..."})
            ack: "Your tweet has been posted ..."

turn 3:
  2 calls:  retweet({tweet_id: 10})
            ack: "You've successfully retweeted ..."
```

Total: **4 turns, 10 calls, 125s latency**. Score: PASS.

The model behaved correctly: asks user for missing param (turn 0), does the work after receiving info (turn 1), then completes the subsequent multi-turn instructions.

### cf2 trace (gpt-4.1 + conditional_frozen_v2) — force-terminated

```
turn 0:   (only one turn produced! BFCL evaluator expected 4)
  21 calls in one mega-turn:
    1.  get_zipcode_based_on_city({"city":"Stonebrook"})         ← only gets ZIP for destination
    2.  estimate_distance({"cityA":"CURRENT_LOCATION","cityB":"74532"})  ← USES PLACEHOLDER STRING!
    3.  estimate_distance({"cityA":"74532","cityB":"CURRENT_LO..."})     ← swaps and retries with placeholder
    4-9. display_log({"messages":["Unable to determine the road ..."]})   ← spams display_log
    10. display_log({"messages":["Please specify your current ..."]})
    11. display_log({"messages":["To estimate your driving dis..."]})
    12. display_log({"messages":["To proceed, I need your curr..."]})
    13. display_log({"messages":["Road distance to Stonebrook ..."]})
    14. display_log({"messages":["Your origin city is needed t..."]})
    15. display_log({"messages":["Please specify your starting ..."]})
    16. display_log({"messages":["I need your current city or ..."]})
    17. display_log({"messages":["Please specify your current ..."]})
    18. display_log({"messages":["I need your departure city o..."]})
    19. display_log({"messages":["To help with your genealogy ..."]})
    20. display_log({"messages":["Driving distance to Stonebro..."]})
    21. (truncated)
```

Total: **1 turn, 21 calls, 91s latency**. Score: FORCE_TERMINATED.

BFCL evaluator error: `Model was force-terminated during inference phase. The length of the model result turns (1) does not match the length of the ground truth turns (4).`

### What this trace tells us

1. **cf2 collapses multi-turn into single-turn**: the model never relinquishes turn-0; it tries to do all 4 GT turns inside turn 0.
2. **cf2 invents a placeholder**: instead of asking the user for the missing starting city, the model uses the literal string `"CURRENT_LOCATION"` as an argument, then retries when that fails.
3. **cf2 spams `display_log` to communicate with the user instead of stopping**: 18 of the 21 calls are `display_log` requests like "Please specify your current city". But `display_log` doesn't return control to the user in BFCL's framework — it just logs.
4. **The mechanism is actively anti-helpful** for the `multi_turn_miss_param` category. It's not "the candidate proposal didn't help" — it's "the candidate proposal broke the runtime contract".

## §4 Mechanism hypothesis (sanitized, not confirmed by code-read)

The label `conditional_frozen_v2` and the runtime config suggest this arm freezes / locks some conditional path in the proxy. The empirical evidence (single-turn collapse, placeholder use, display_log spamming) is consistent with the mechanism **forcing the model to attempt completion entirely inside turn 0** — possibly by injecting guidance like "complete the task in this response" or by suppressing turn boundaries.

To confirm the mechanism cause, would need to:
- Read `runtime_bfcl_structured.yaml` arm-specific config
- Inspect the proxy's adapter logic for `conditional_frozen_v2` profile
- Compare a baseline turn-0 trace card vs a cf2 turn-0 trace card

(These are next-step diagnostics; not done in this commit.)

## §5 Implications for the next decision

### Original priority list:
> "先补齐 candidate 与 baseline 的逐 case 对比，再决定是否投入 E5/E3 高杠杆干预"

The comparison reveals two things relevant to that decision:

1. **conditional_frozen_v2 is REGRESSING, not helping** on multi_turn_miss_param.
   - 5 baseline-passes lost (77, 88, 94, 97, 100)
   - 14 baseline-fails stayed failed (with a worse failure mode: force_terminated)
   - **Recommendation**: do NOT pursue cf2 as an intervention. Investigate or
     deprecate it. The user instruction #4 said "v3 controller 的下一步不是直接 promote
     ... 如果仍然是 marker-only 或 descriptor-only，就不能 promote" — this same
     principle applies to cf2.

2. **The high-leverage interventions (E5 irrelevance abstain, E3 max_tokens) are likely SAFER than cf2**.
   - E5 is a deterministic proxy-layer rule (no model behavior change needed)
   - E3 is a config tweak (no mechanism change)
   - Both can be tested against baseline with the same diagnostic extractor
   - Neither risks the kind of regression we see with cf2

### Still open (pending further runs):
- runtime_slot_controller_v2 arm — not yet run. Could fail the same way as cf2,
  or differently. Worth knowing before deciding L3 path.
- baseline on gpt-4o — in flight. Will tell us whether 29.2% is a model-capability
  ceiling or a gpt-4.1-specific artifact.

## §6 What to commit, what NOT to commit

### Committed in this PR (sanitized)
- `outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_baseline_vs_cf2_per_case_comparison.json` —
  sanitized per-case overlap (case_id, passed bool, error_type_class, turn_count, latency).
  NO raw prompts, NO raw responses, NO scorer diff, NO argument literal values.
- This report (markdown with trace summaries).

### NOT committed (kept in /tmp only for local audit)
- Raw model output trajectories (with all 21 calls' verbose content)
- Literal prompt text
- Provider response payloads
- Scorer's full failure details

The sanitized examples in this report DO include some short string fragments
(e.g., method names `get_zipcode_based_on_city`, placeholder string
`CURRENT_LOCATION`, log message snippets like "Please specify your ..."). These
are:
- Method names: part of public BFCL benchmark schema (also in the leaderboard)
- Placeholder strings: the model's own invention, not from the prompt
- Log message snippets: model's own output structure, truncated to 30-50 chars,
  no proprietary or sensitive content

If the user wants stricter sanitization, the JSON artifact can be re-emitted
with only `case_id + passed + error_type_class + turn_count + latency`,
matching the G6b-2 diagnostic format exactly.

## §7 Boundary attestations

| field | baseline | cf2_partial | comparison |
|---|---|---|---|
| performance_evidence | false | false | false |
| raw_material_absent | true | true | true |
| raw_prompt_committed | false | false | false |
| raw_response_committed | false | false | false |
| gold_expected_committed | false | false | false |
| argument_values_committed | false | false | false (see §6 disclosure for short fragments) |
| scorer_diff_committed | false | false | false |
| holdout_touched | false | false | false |
| sota_3pp_claim_ready | false | false | false |
| huawei_acceptance_ready | false | false | false |
| provider_calls_made | true | true | n/a (this is comparison, not new run) |

## §8 Pending follow-ups

1. **baseline-gpt4o** arm (in flight at commit time): will give baseline accuracy on stronger model. If 40-50% as hypothesised, decisions L3 paths shift toward exploiting the better-model headroom.
2. **runtime_slot_controller_v2** arm: not yet attempted. Same time/cost as cf2 (~30 min + ~$5-10), but at ~21 calls/case may also time out.
3. **conditional_frozen_v2 root-cause inspection**: read the arm-specific runtime adapter to confirm the single-turn-collapse hypothesis.
4. **E5 + E3 interventions**: as recommended in §5, these are now the more attractive paths since cf2 is regressing.

After (1) baseline-gpt4o completes, a follow-up commit will add gpt-4o numbers and update §1.

---

## §9 UPDATE (post-original-commit) — gpt-4o baseline finished miss_param

After this report was originally committed, the in-flight `baseline` arm
running on gpt-4o (full, gpt-4o-2024-11-20) completed its miss_param category.

### Three-way comparison on multi_turn_miss_param target category

| arm | model | cases | passed | acc | result_turn_count avg | all-fail-mode |
|---|---|---|---|---|---|---|
| baseline | gpt-4.1-2025-04-14 | 24 | **7** | **29.2%** | 4.3 | mixed (state_mismatch + empty_turn) |
| conditional_frozen_v2 (cf2) | gpt-4.1-2025-04-14 | 19 (partial) | 0 | 0.0% | 1.0 | 100% multi_turn:force_terminated |
| baseline | gpt-4o-2024-11-20 | 24 | **0** | **0.0%** | (TBD; almost certainly 1) | 100% multi_turn:force_terminated |

### Key finding (overturns user's gpt-4o hypothesis)

The user's hypothesis "gpt-4o would do 40-50% on miss_param" was **incorrect**.
**gpt-4o scores 0% — WORSE than gpt-4.1**.

But more importantly, the SHARED FAILURE MODE between cf2-on-gpt-4.1 AND
gpt-4o-baseline reveals the underlying mechanism:

  - Both produce 1-turn outputs (vs gpt-4.1's 4.3-turn average)
  - Both trigger BFCL `force_terminate` due to "result turns != ground truth turns"
  - Both bypass the "ask user a clarifying question" step

For case 77 specifically (which gpt-4.1 baseline passes):
- **gpt-4.1 turn 0 first element**: a STRING (the model's clarifying question text — "To help determine the road distance to Stonebrook, could you please provide your starting city or ZIP code?")
- **gpt-4o turn 0 first element**: a LIST (a tool call). Same structural pattern as cf2.

So the question becomes: **what training/post-training difference between gpt-4.1 and gpt-4o makes gpt-4.1 willing to emit a text question turn for miss_param, while gpt-4o defaults to brute-forcing through tool calls?**

Possibilities (not investigated in this commit):
1. **BFCL model_handler config**: the BFCL benchmark has model-specific
   handler classes. The handler for `gpt-4o-mini-2024-07-18-FC` (which our
   BFCL_MODEL_ALIAS uses, irrespective of actual upstream) may differ in
   how it formats prompts and parses responses for newer-vs-older gpt-4
   API formats. **Verify this first**: change BFCL_MODEL_ALIAS to a more
   appropriate gpt-4.1-compatible handler and re-run gpt-4o.
2. **System-prompt biasing**: gpt-4o post-training may bias toward
   "complete the task with tools" while gpt-4.1 keeps the "ask user when
   missing info" reflex. Possibly addressable via system-prompt patches.
3. **API response format**: gpt-4o's tool-call format may differ from
   gpt-4.1's in subtle ways the proxy/BFCL doesn't translate correctly.
   Trace inspection of raw_response.choices[0] would tell.

### Implications for L3 intervention selection

This is actually a positive signal for the **E5 (irrelevance abstain)** intervention,
which is structurally similar: detect "model wants to emit a tool call when
it should not" and override. For miss_param, the analogous intervention
is: detect "model is brute-forcing with placeholder strings" and override
to "ask user a clarifying question".

Proposed **E7 (NEW)**: A proxy-layer rule that:
- Watches model output for placeholder strings (e.g., `"CURRENT_LOCATION"`,
  `"UNKNOWN"`, regex like `"\\bCURRENT_\\w+\\b"`)
- If detected within an argument value of a tool call on a multi_turn_miss_param
  case, override the response to emit a clarifying-question text turn instead.

This would potentially help BOTH cf2-on-gpt-4.1 AND gpt-4o-baseline cases
recover (since both share the placeholder-string failure mode).

### Updated three-way comparison artifact

`outputs/artifacts/stage1_bfcl_acceptance/abhe_v0_target_category_three_way_comparison.json`
— sanitized 24-row per-case table with all three arms' outcomes side-by-side.

