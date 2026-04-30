# Deprecated OpenRouter Notes

Deprecated for the Stage-1 BFCL sprint: use `novacode` / 创智 via `NOVACODE_API_KEY`; do not use OpenRouter.

仓库根目录以下记为 `$REPO`（例如 `/cephfs/qiuyn/training-free`）。

---

## 1. 进入仓库并激活 conda

```bash
cd "$REPO"
conda activate tf
python -V   # 建议 >= 3.10
```

---

## 2. 安装 Python 依赖（在 `tf` 内，不要用 `scripts/install_bfcl.sh` 创建 `.venv`）

`install_bfcl.sh` 会新建 `.venv`，与 conda 冲突。在已激活的 `tf` 中执行：

```bash
pip install -U pip
pip install -e .
pip install "bfcl-eval==2025.12.17"
```

确认命令可用：

```bash
which grc
which bfcl
```

---

## 3. 初始化 BFCL 评测目录（`.env` 与用例列表）

```bash
bash scripts/init_bfcl_project_root.sh
```

会在 `outputs/bfcl_v4/baseline/bfcl/` 写入从 `bfcl_eval` 包拷贝的 `.env` 与 `test_case_ids_to_generate.json`。  
BFCL 通过本机 `grc` 代理调模型，一般**不必**在 BFCL 的 `.env` 里填 OpenAI；若评测报错缺变量，再打开该 `.env` 按 `bfcl-eval` 文档补全（多数场景只需保证 `LOCAL_SERVER_*` 由运行脚本导出）。

---

## 4. 每次实验前加载协议与 OpenRouter 环境变量

```bash
cd "$REPO"
conda activate tf
source configs/bfcl_v4_phase1.env
source configs/bfcl_v4_openrouter.env

export OPENROUTER_API_KEY="sk-or-v1-..."
export OPENROUTER_HTTP_REFERER="https://你的实验室或机构域名"
export OPENROUTER_X_TITLE="training-free"
```

模型变量分两层，不能混用：

- `GRC_BFCL_MODEL`：传给 `bfcl --model` 的 evaluator alias，必须存在于 `bfcl_eval.constants.model_config.MODEL_CONFIG_MAPPING`，默认 `gpt-4o-mini-2024-07-18-FC`。
- `GRC_UPSTREAM_MODEL`：`grc serve` 实际转发到 OpenRouter 的模型路由，默认 `x-ai/grok-3-beta`。

更换 OpenRouter 实际上游模型时：

```bash
export GRC_UPSTREAM_MODEL="anthropic/claude-3.5-sonnet"
```

**跑 BFCL 时**，`run_bfcl_v4_baseline.sh` 的第一个参数传给 `bfcl` 的 `--model`，应使用 `GRC_BFCL_MODEL`，不要传 OpenRouter route：

```bash
bash scripts/run_bfcl_v4_baseline.sh "${GRC_BFCL_MODEL}"
```

---

## 5. 连通性检查（推荐）

```bash
bash scripts/run_phase1_smoke.sh
```

成功则说明本机 `grc` 代理可访问 OpenRouter 并完成一次 `chat.completions` 链路。

---

## 6. 正式基线

```bash
bash scripts/run_bfcl_v4_baseline.sh "${GRC_BFCL_MODEL}"
```

全量时间较长；可先子集：

```bash
export GRC_BFCL_TEST_CATEGORY="你的类别"
bash scripts/run_bfcl_v4_baseline.sh "${GRC_BFCL_MODEL}"
```

---

## 常见问题

- **`missing env var: OPENROUTER_API_KEY`**：未 export 密钥，或 shell 与运行脚本的会话不一致。  
- **`upstream.base_url is not configured`**：`GRC_UPSTREAM_PROFILE` 未设为 `openrouter` 或 profile 未加载；检查是否已 `source configs/bfcl_v4_phase1.env`。  
- **`httpx.ConnectError` / `[Errno 111] Connection refused`（指向本机）**：`bfcl` 在连本地 `grc` 代理时失败。常见原因：(1) 代理未启动或已退出，查看 `/tmp/grc_baseline_proxy.log` 或 `/tmp/grc_patch_proxy.log`；(2) **端口不一致**：`run_bfcl_v4_patch.sh` 默认在本机 **8012** 起代理，而 `bfcl_eval` 拷贝的 `.env` 常写死 **8011**。当前 `run_bfcl_v4_baseline.sh` / `run_bfcl_v4_patch.sh` 会在启动代理时导出 `OPENAI_BASE_URL=http://127.0.0.1:<端口>/v1`，请使用仓库内最新脚本；若仍失败，检查 `${BFCL_PROJECT_ROOT}/.env` 是否把 `OPENAI_BASE_URL` 设成与当前 `LOCAL_SERVER_PORT` 冲突的地址（可注释掉该行后重试）。  
- **Novacode**：若以后能访问 Novacode，执行 `export GRC_UPSTREAM_PROFILE=novacode` 并配置 `NOVACODE_*` 即可，无需改代码。
