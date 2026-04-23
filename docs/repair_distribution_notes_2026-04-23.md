# Repair Distribution Notes (2026-04-23)

这份备忘用于记录当前对 `repair` 分布的阶段性判断，避免后续推进 Phase-2 / policy 工作时丢失分析脉络。

## 当前主要分布

聚焦 `multi_turn_miss_param`：

### baseline

- `coerce_no_tool_text_to_empty = 128`
- `strip_assistant_content_with_tool_calls = 63`
- `resolve_contextual_string_arg = 52`

### primary_v4

- `coerce_no_tool_text_to_empty = 429`
- `strip_assistant_content_with_tool_calls = 43`
- `resolve_contextual_string_arg = 67`

### rerun_v4

- `coerce_no_tool_text_to_empty = 421`
- `strip_assistant_content_with_tool_calls = 38`
- `resolve_contextual_string_arg = 76`

## 关键启发

### 1. 当前真正的大头 repair 不是参数修补，而是 no-tool prose coercion

`coerce_no_tool_text_to_empty` 从 baseline 的 `128` 次直接跳到 `400+` 次，远高于另外两类 repair。  
这说明当前 Phase-2 patch line 触发后的主要运行时动作，并不是把已有 tool call 修得更合法，而是在大量处理“本该继续 tool use，却输出了 prose”的情况。

这和当前主 failure family 是一致的：系统现在主要在对抗 `premature stop / no-tool decision`，而不是 schema-level 错误。

### 2. `coerce_no_tool_text_to_empty` 更像在控制症状，还没有充分转化成下一步动作

到了 `primary_v4 / rerun_v4`，虽然 `coerce_no_tool_text_to_empty` 大量触发，但 failure summary 里仍然有很高的：

- `empty_tool_call`
- `post_tool_prose_summary`
- `termination_inadmissible`

例如：

### primary_v4 残余 failure

- `empty_tool_call = 486`
- `post_tool_prose_summary = 279`
- `termination_inadmissible = 339`

### rerun_v4 残余 failure

- `empty_tool_call = 496`
- `post_tool_prose_summary = 269`
- `termination_inadmissible = 324`

这说明当前这类 repair 更像是在把不该出现的 prose 清掉，避免 structured client 被污染，但还没有把大量 case 真正推进成正确的下一步 tool action。

结论：

- 它是有价值的。
- 但价值更偏防御性、约束性。
- 它还不是系统最终能力来源。

### 3. `resolve_contextual_string_arg` 的持续存在说明显式 literal grounding 是有效方向

这类 repair 从 `52 -> 67 -> 76`，没有消失，反而在后两轮略上升。  
这说明在 multi-turn harder slice 上，“模型已经大致知道要做什么，但参数仍然写得很模糊”的问题是真实存在的。

这对下一步有两个直接启发：

- `prior_explicit_literals_present` 这类 predicate 值得保留。
- future policy / compiler 不能只盯“是否继续”，还要盯“继续时是否能复用已有 literal”。

换句话说，下一步的 policy unit 不能只会说“继续”，还要更明确表达“继续时优先重用已有显式值”。

### 4. `strip_assistant_content_with_tool_calls` 更像 hygiene，不是主矛盾

它在 baseline 是 `63`，到 `primary_v4 / rerun_v4` 反而降到 `43 / 38`。  
这类 repair 的意义更多是：模型已经发了 tool call，但顺手又写了一段 narration，需要 runtime 清理一下。

所以它依然重要，但不应该成为下一轮主攻方向。  
它更像“保持输出结构干净”的配套措施，而不是 top-line gain 的主要来源。

## 与当前 repair 分类的一致性

当前脚本已经把 repair 明确分成两类：

- `compatibility`
- `decision_adjacent`

其中：

- `resolve_contextual_string_arg` 属于 `compatibility`
- `coerce_no_tool_text_to_empty` 和 `strip_assistant_content_with_tool_calls` 属于 `decision_adjacent`

这个划分很关键，因为它帮助回答一个核心问题：

当前收益到底来自“格式修干净了”，还是来自“决策层开始变了”。

从分布上看，当前最活跃的是 `decision_adjacent` repair；但从 failure 残余上看，decision 层问题仍然很重。  
因此下一步的重心应该从“repair 继续加码”转向“policy 真正接管”。

## iter_004_execute 当前补充

截至 2026-04-23 本次检查，`iter_004_execute` 已完成 target 和 holdout，paired rerun 仍在运行。

### target: `multi_turn_miss_param`

- accuracy: `42.0%` (`84 / 200`)
- trace count: `2734`
- all stored trace HTTP status: `200`
- request patches present: `2733` traces
- residual validation issues:
  - `empty_completion = 480`
  - `termination_inadmissible = 344`
  - `post_tool_prose_summary = 282`
  - `clarification_request = 87`
  - `actionable_no_tool_decision = 62`
- repairs:
  - `coerce_no_tool_text_to_empty = 431`
  - `resolve_contextual_string_arg = 62`
  - `strip_assistant_content_with_tool_calls = 33`
- `force_terminated = 0`

### holdout: `simple_python`

- accuracy: `95.0%` (`380 / 400`), matching the baseline holdout.
- validation issues: `0`
- repairs: only `resolve_contextual_string_arg = 5`
- `force_terminated = 0`

Interpretation: the current candidate improves the target over baseline and `primary_v4` without observed `simple_python` regression, but it is still not a formal claim because paired rerun and selector acceptance are pending. Residual target failures remain concentrated in empty/no-tool and wrong-stop behavior, so the next policy work should still focus on `ACTIONABLE_NO_TOOL_DECISION` and `POST_TOOL_PROSE_SUMMARY`, not broad compatibility expansion.


## 下一步建议

### 1. 不要继续把主要精力放在新增 repair 种类上

现有 repair 分布已经说明，主问题不是“还缺一个新 repair”，而是“已有 repair 已经大量触发，但很多 case 仍停留在 no-tool / wrong-stop 失败上”。

### 2. 重点分析 repair × failure family 交叉表，而不是只看总数

最该回答的问题是：

- `coerce_no_tool_text_to_empty` 主要打在 `POST_TOOL_PROSE_SUMMARY` 上，还是 `ACTIONABLE_NO_TOOL_DECISION` 上？
- 它在哪一类上的 success 更高？
- `resolve_contextual_string_arg` 的 success 是否主要集中在 `ARG_UNDERSPECIFIED`？

这一层分析会比总 repair count 更有价值。  
当前脚本已经开始支持按 family 做 attribution，这一步应该尽快跑起来。

### 3. 主攻 family 应收缩到 `ACTIONABLE_NO_TOOL_DECISION + POST_TOOL_PROSE_SUMMARY`

原因有两点：

- repair 分布显示最常被干预的是 no-tool prose。
- failure 分布显示当前残余最大的问题也仍然围绕 no-tool / wrong-stop。

因此下一轮最合理的目标不是继续优化 `strip_assistant_content_with_tool_calls`，而是让 policy unit 真正把“继续执行”转成 tool action，而不是只把 prose 清空。

### 4. 重新定义 repair 的角色：诊断器和守门员，而不是主角

当前分布已经说明 repair 很重要，但如果在论文或汇报里把主要贡献讲成 repair，会比较危险。

更稳的表述应该是：

- repair 帮助揭示系统在哪些 failure family 上仍然处于被动兜底状态。
- 真正的下一阶段目标，是把这些兜底点逐步转化成显式 decision policy 的主动控制。

## 一句话总结

**当前 repair 分布的最大启发，不是“还要再发明更多 repair”，而是“系统的主矛盾已经非常明确地暴露在 no-tool / wrong-stop 上，下一步必须从 repair-heavy 转向 policy-heavy”。**
