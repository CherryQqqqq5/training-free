# Golden Rule Compiler

面向 BFCL 的 training-free tool-use harness/compiler 实验仓库。

当前 Phase-1 的目标不是改底模权重，而是验证一个更外层的命题:
把失败轨迹编译成可执行、可验证、可回滚的 harness patch，是否能在 BFCL 上带来稳定收益。

## 一句话主张

我们把 Phase-1 收敛为:
**BFCL-first 的 Golden Rule Compiler**。

核心方法是:

1. 跑通官方 BFCL 评测链路和可复现 baseline。
2. 从失败轨迹中抽取结构化 failure evidence。
3. 将 failure evidence 编译为 rule/harness patch。
4. 把 patch 作用到 prompt、tool guard、argument sanitizer、verification hook、fallback routing。
5. 用 BFCL 指标和 Pareto 规则决定 patch 是否被保留。

## 当前状态

仓库已经完成的部分:

1. **BFCL-first 协议固定**。评测版本、复现锚点、baseline/patch runner、artifact shape 已固定。
2. **外部 evaluator + 本地 proxy harness**。BFCL evaluator 保持外置，仓库只提供 OpenAI-compatible 代理与 rule runtime。
3. **显式 IR 与编译入口**。当前主链路是 `FailureTrace -> FailureIR -> RuleIR -> PatchBundle -> ValidationRecord`。
4. **多落点 runtime hook**。已支持 request-side prompt injection，response-side tool guard、argument sanitizer、verification hook、fallback routing。
5. **候选 patch 生命周期**。已支持 `rules/candidates/`、`rules/accepted/`、`rules/rejected/`、`rules/active/`。
6. **Pareto selector**。当前选择标准基于 `acc / cost / latency / regression`。

当前还没有完成的部分:

1. **Meta-Harness 风格的 code-space search** 还没有实现。
2. **历史候选上的 outer-loop search** 还没有实现。
3. **推荐工具 / stop condition / richer preconditions** 还不是一等 IR 字段。
4. **失败挖掘到有效 patch 的闭环** 还不稳定。当前仓库内已提交的一批 candidate 里，存在 mined failures 为空、最终 rule bundle 为空的情况。

这意味着:
现在的仓库已经是一个可运行的 Phase-1 scaffold，但还不是“已验证 patch 能稳定提升 BFCL 分数”的完成版。

## Phase-1 技术定义

### 研究对象

Phase-1 研究的是 **tool-use harness/compiler**，不是模型训练。

系统输入:

1. BFCL 发给代理的 OpenAI-compatible request
2. 上游模型原始 response
3. 运行时修补与验证记录
4. 评测最终得分与汇总指标

系统输出:

1. `rule.yaml` 形式的 patch bundle
2. `metrics.json`
3. `repairs.jsonl`
4. `failure_summary.json`
5. `accept.json`

### Golden Rule IR

当前仓库已把“golden rule”压缩为可执行 IR，定义见 [src/grc/compiler/ir.py](src/grc/compiler/ir.py) 和 [docs/golden_rule_onepager.md](docs/golden_rule_onepager.md)。

现阶段核心字段包括:

1. `trigger`
2. `scope`
3. `action`
4. `validation_contract`
5. `retention`

与会议版本的一一对应关系:

1. `trigger` 已落地
2. `preconditions` 目前部分吸收到 `trigger + scope`
3. `forbidden_actions` 目前主要落在 `tool_guard`
4. `arg_constraints` 已落在 `arg_sanitizer`
5. `verification` 已落在 `validation_contract`
6. `recovery` 已落在 `fallback_router`
7. `recommended_tools` 尚未成为一等字段
8. `stop_condition` 尚未成为一等字段

### Compiler 落点

当前 compiler 不修改 BFCL evaluator 内部逻辑，而是把 patch 编译到外部 harness 中:

1. `prompt_injector`
2. `tool_guard`
3. `arg_sanitizer`
4. `verification_hook`
5. `fallback_router`

对应实现分别见:

1. [src/grc/compiler/trace_to_patch.py](src/grc/compiler/trace_to_patch.py)
2. [src/grc/runtime/engine.py](src/grc/runtime/engine.py)
3. [src/grc/runtime/sanitizer.py](src/grc/runtime/sanitizer.py)
4. [src/grc/runtime/validator.py](src/grc/runtime/validator.py)

### Validation / Selection

Phase-1 不是“写条规则就接受”，而是按指标采纳:

1. `acc` 不下降
2. `cost` 不上升
3. `latency` 不上升
4. `regression` 不恶化
5. 至少一项严格更优

选择器实现见 [src/grc/selector/pareto.py](src/grc/selector/pareto.py)。

## 三层拆解

### 第一层: 直接复用或强借鉴开源

1. benchmark 官方评测脚本
2. 数据格式适配
3. 基础 tool-calling loop
4. 日志记录
5. 结果汇总
6. 环境配置

当前仓库的做法是:
**保留 BFCL evaluator 外置，仓库只包一层代理与编译器。**

### 第二层: 在开源基础上轻改

1. prompt template
2. memory / trace shape
3. tool wrapper 接口
4. verifier
5. 错误分类与归因

当前仓库已经轻改并实现了:

1. request-side prompt injection
2. trace mining
3. runtime validation issue recording
4. artifact aggregation

### 第三层: 自研核心

1. Golden Rule IR
2. failure trace -> rule patch 的 compiler
3. patch -> harness 的编译逻辑
4. patch 的 validation / selection / retention
5. rule 对 prompting / guard / sanitizer / verification / fallback 的作用机制

这是本仓库真正的研究重心。

## 仓库结构

```text
src/grc/compiler/        trace mining、IR、trace -> patch compiler
src/grc/runtime/         proxy、rule engine、sanitizer、validator、trace store
src/grc/selector/        patch selection / Pareto logic
configs/                 BFCL protocol、runtime config、selector/compiler config
scripts/                 baseline、patch、smoke、aggregation、Phase-1 loops
rules/                   seed / candidate / accepted / rejected / active rules
docs/                    one-pager、protocol、failure taxonomy、setup docs
outputs/                 已生成的 baseline / patch / report / artifact 示例
tests/                   selector 与 BFCL aggregation 测试
```

## BFCL-first 协议

当前固定协议见 [docs/experiment_protocol_bfcl_v4.md](docs/experiment_protocol_bfcl_v4.md)。

关键约束:

1. evaluator package 固定为 `bfcl-eval==2025.12.17`
2. reproduction anchor 固定为 `f7cf735`
3. 默认优先跑 BFCL evaluator 的 full-suite
4. baseline 和 candidate 必须共用同一协议
5. evaluator internals 不在 Phase-1 中修改

环境变量固定入口见 [configs/bfcl_v4_phase1.env](configs/bfcl_v4_phase1.env)。

## 快速开始

推荐工作流: **conda + OpenRouter**。

完整说明见 [docs/setup_conda_openrouter.md](docs/setup_conda_openrouter.md)。

### 1. 安装依赖

```bash
conda activate tf
pip install -U pip
pip install -e .
pip install "bfcl-eval==2025.12.17"
```

或使用本地 `.venv`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
bash scripts/install_bfcl.sh
```

### 2. 初始化 BFCL 目录

```bash
bash scripts/init_bfcl_project_root.sh
```

### 3. 加载协议和上游配置

```bash
source configs/bfcl_v4_phase1.env
source configs/bfcl_v4_openrouter.env

export OPENROUTER_API_KEY="..."
export OPENROUTER_HTTP_REFERER="https://your-lab.example"
```

注意两层模型配置不要混用:

1. `GRC_BFCL_MODEL`: 传给 `bfcl --model` 的 evaluator alias
2. `GRC_UPSTREAM_MODEL`: `grc serve` 实际转发到上游的 provider route

### 4. smoke test

```bash
bash scripts/run_phase1_smoke.sh
```

### 5. 跑 baseline

全量默认流程:

```bash
bash scripts/run_bfcl_v4_baseline.sh "${GRC_BFCL_MODEL}"
```

子集 ablation:

```bash
export GRC_BFCL_TEST_CATEGORY="simple_python"
bash scripts/run_bfcl_v4_baseline.sh "${GRC_BFCL_MODEL}"
```

## 编译闭环

### 单次闭环

1. 从 baseline traces 中挖 failure

```bash
grc mine \
  --trace-dir outputs/bfcl_v4/baseline/simple_python/traces \
  --out outputs/reports/simple_python_failures.jsonl
```

2. 从 failure 编译 candidate patch

```bash
grc compile \
  --failures outputs/reports/simple_python_failures.jsonl \
  --out rules/candidates/patch_simple_python_001/rule.yaml \
  --patch-id patch_simple_python_001 \
  --candidate-dir rules/candidates/patch_simple_python_001
```

3. 运行 patch 版本

```bash
bash scripts/run_bfcl_v4_patch.sh \
  "${GRC_BFCL_MODEL}" \
  outputs/bfcl_v4/patch/simple_python \
  8012 \
  "simple_python" \
  configs/runtime.yaml \
  rules/candidates/patch_simple_python_001 \
  outputs/bfcl_v4/patch/simple_python/traces \
  rules/candidates/patch_simple_python_001 \
  outputs/bfcl_v4/baseline/simple_python/artifacts/metrics.json
```

4. 选择并归档 patch

```bash
grc select \
  --baseline-metrics outputs/bfcl_v4/baseline/simple_python/artifacts/metrics.json \
  --candidate-metrics rules/candidates/patch_simple_python_001/metrics.json \
  --candidate-dir rules/candidates/patch_simple_python_001 \
  --rule-path rules/candidates/patch_simple_python_001/rule.yaml \
  --accepted-dir rules/accepted \
  --rejected-dir rules/rejected \
  --active-dir rules/active \
  --out rules/candidates/patch_simple_python_001/accept.json
```

### 四个子集的 Phase-1 loop

```bash
bash scripts/run_phase1_four_subset_e2e.sh "${GRC_BFCL_MODEL}"
```

当前脚本会按以下 BFCL 子集运行:

1. `simple_python`
2. `multiple`
3. `parallel_multiple`
4. `multi_turn_miss_param`

## 产物约定

每次 run 至少产出:

1. `metrics.json`
2. `repairs.jsonl`
3. `failure_summary.json`

每个 candidate 目录还应包含:

1. `rule.yaml`
2. `accept.json`

归档规则:

1. accepted candidate -> `rules/accepted/<patch_id>/`
2. rejected candidate -> `rules/rejected/<patch_id>/`
3. active runtime rule -> `rules/active/<patch_id>.yaml`

当前仓库里的示例产物可以帮助你核对目录形状，但不应被当成“已经完成研究结论”的证据。

## 已知问题与边界

1. **当前一些已提交 candidate 是空 patch**。这通常意味着对应 trace mining 没挖出 failure case，或 baseline trace 里没有被当前 miner 捕获的错误模式。
2. **当前 failure mining 偏 schema-level**。对更复杂的 sequential / planning / stateful failure 仍然覆盖不足。
3. **当前 selector 是静态 Pareto rule**，不是 learned selector，也不是历史候选上的 search policy。
4. **当前 patch 落点是 deterministic runtime hook**，还不是更广义的 code-space harness rewrite。
5. **README 中写的是“当前阶段的真实现状”**，不是最终论文 claim。

## 文档

1. 环境配置: [docs/setup_conda_openrouter.md](docs/setup_conda_openrouter.md)
2. 方法一页纸: [docs/golden_rule_onepager.md](docs/golden_rule_onepager.md)
3. 失败分类词表: [docs/failure_taxonomy.md](docs/failure_taxonomy.md)
4. BFCL Phase-1 协议: [docs/experiment_protocol_bfcl_v4.md](docs/experiment_protocol_bfcl_v4.md)

## 后续规划

### P0: 先把闭环跑实

1. 修复 `mine -> compile` 在真实 baseline traces 上经常产出空 `failures.jsonl` 的问题。
2. 为常见 BFCL failure 补充更稳定的 mined signal，至少覆盖 `empty_tool_call`、`wrong_tool_name`、`invalid_json_args`、`missing_required`、`type_mismatch`。
3. 让四个子集里至少有一个能稳定产出非空 candidate，并完成一次有效的 accept/reject。

### P1: 把 compiler 从“schema 修补器”提升为“failure-to-patch compiler”

1. 把 `preconditions` 从隐式表达改成显式字段。
2. 增加 `recommended_tools` 和 `stop_condition`。
3. 扩展 rule 触发条件，引入 task/state/log pattern 级别的 trigger。
4. 让 compiler 能针对不同 failure class 生成更区分化的 patch，而不是主要收敛到 sanitizer/guard。

### P2: 引入更像 Meta-Harness 的外循环

1. 记录 candidate 历史和证据样本，形成 filesystem history。
2. 实现基于历史 evidence 的 patch proposal / mutation / retention。
3. 支持多 candidate 比较，而不是单 candidate vs baseline。
4. 从“单步 compile”升级到“outer-loop search over harness patches”。

### P3: 从 patch bundle 走向 code-space search

1. 把 patch 作用点从 runtime config 扩展到更广义 harness code region。
2. 引入局部 code-space search，而不是只改 YAML bundle。
3. 把选择对象从“规则文件”扩展到“可验证 harness candidate”。

### Phase-1 完成标准

满足以下条件时，才算真正完成你要的这版 Phase-1:

1. BFCL-first baseline 协议稳定、可复现。
2. 至少一个强 baseline 在官方链路下固定下来。
3. failure trace -> rule patch -> harness patch 的闭环能稳定产生非空候选。
4. 至少一个候选在 BFCL 某个正式子集上被 selector 接受。
5. README、one-pager、协议文档与代码状态保持一致。
