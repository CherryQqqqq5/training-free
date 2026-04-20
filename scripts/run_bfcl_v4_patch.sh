#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${REPO_ROOT}/configs/bfcl_v4_phase1.env"

BFCL_RUNTIME_CONFIG_DEFAULT="${GRC_BFCL_RUNTIME_CONFIG:-${REPO_ROOT}/configs/runtime_bfcl_structured.yaml}"

grc_wait_proxy_healthy() {
  local port="$1"
  local log_path="$2"
  local i
  for i in $(seq 1 60); do
    if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  echo "error: grc proxy did not respond on http://127.0.0.1:${port}/health within 60s" >&2
  echo "       check server log: ${log_path}" >&2
  return 1
}

bfcl_fix_result_layout() {
  local bfcl_root="$1"
  local nested_result_dir="${bfcl_root}/${bfcl_root}/result"
  local canonical_result_dir="${bfcl_root}/result"
  if [[ ! -d "${nested_result_dir}" ]]; then
    return 0
  fi
  mkdir -p "${canonical_result_dir}"
  cp -R "${nested_result_dir}/." "${canonical_result_dir}/"
}

write_run_manifest() {
  local out_path="$1"
  local rules_dir="$2"
  local rule_path="$3"
  local run_id="$4"

  local git_sha
  git_sha="$(cd "${REPO_ROOT}" && git rev-parse HEAD 2>/dev/null || echo unknown)"
  local git_dirty=false
  if ! (cd "${REPO_ROOT}" && git diff --quiet --ignore-submodules HEAD -- 2>/dev/null); then
    git_dirty=true
  fi

  python3 - "$out_path" "$rules_dir" "$rule_path" "$run_id" "$git_sha" "$git_dirty" <<"PY"
import json
import os
import sys
from datetime import datetime, timezone

out_path, rules_dir, rule_path, run_id, git_sha, git_dirty = sys.argv[1:7]
manifest = {
    "bfcl_model_alias": os.environ.get("BFCL_MODEL", ""),
    "upstream_profile": os.environ.get("GRC_UPSTREAM_PROFILE", ""),
    "upstream_model_route": os.environ.get("GRC_UPSTREAM_MODEL", ""),
    "protocol_id": os.environ.get("GRC_PROTOCOL_ID", ""),
    "test_category": os.environ.get("TEST_CATEGORY", ""),
    "lane": "compiler_patch",
    "source": "failure_to_policy",
    "git_sha": git_sha,
    "git_dirty": git_dirty == "true",
    "runtime_config_path": os.environ.get("CONFIG_PATH", ""),
    "rules_dir": rules_dir,
    "rule_path": rule_path,
    "run_id": run_id,
    "timestamp": datetime.now(timezone.utc).isoformat(),
}
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, ensure_ascii=False, indent=2)
PY
}

BFCL_CLI=(python "${REPO_ROOT}/scripts/run_bfcl_cli.py")

clean_run_state() {
  if [[ "${GRC_BFCL_CLEAN_RUN:-1}" != "1" ]]; then
    return 0
  fi
  rm -rf "${BFCL_ROOT}/result" "${BFCL_ROOT}/score" "${BFCL_ROOT:?}/${BFCL_ROOT#/}/result" "${TRACE_DIR}"
}

BFCL_MODEL="${1:-${GRC_BFCL_MODEL}}"
RUN_ROOT="${2:-${REPO_ROOT}/outputs/bfcl_v4/patch}"
PORT="${3:-8012}"
TEST_CATEGORY="${4:-${GRC_BFCL_TEST_CATEGORY}}"
CONFIG_PATH="${5:-${BFCL_RUNTIME_CONFIG_DEFAULT}}"
RULES_DIR="${6:-${REPO_ROOT}/rules/active}"
TRACE_DIR="${7:-${RUN_ROOT}/traces}"
ARTIFACT_DIR="${8:-${RUN_ROOT}/artifacts}"
BASELINE_METRICS="${9:-}"
RULE_PATH="${10:-${RULES_DIR}/rule.yaml}"
RUN_ID="${11:-candidate_${TEST_CATEGORY:-all}}"
BFCL_ROOT="${RUN_ROOT}/bfcl"
BFCL_RESULT_DIR="${BFCL_ROOT}/result"
BFCL_SCORE_DIR="${BFCL_ROOT}/score"

clean_run_state

mkdir -p "${BFCL_ROOT}" "${TRACE_DIR}" "${ARTIFACT_DIR}"
export BFCL_MODEL TEST_CATEGORY CONFIG_PATH
export BFCL_PROJECT_ROOT="${BFCL_ROOT}"
export LOCAL_SERVER_ENDPOINT=http://127.0.0.1
export LOCAL_SERVER_PORT="${PORT}"
export OPENAI_BASE_URL="http://127.0.0.1:${PORT}/v1"
export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"

python "${REPO_ROOT}/scripts/sync_bfcl_fixture_env.py" --bfcl-root "${BFCL_ROOT}" --openai-base-url "${OPENAI_BASE_URL}" --local-server-endpoint "${LOCAL_SERVER_ENDPOINT}" --local-server-port "${LOCAL_SERVER_PORT}" --openai-api-key "${OPENAI_API_KEY}"

PROXY_PID=""
cleanup() {
  if [[ -n "${PROXY_PID}" ]]; then
    kill "${PROXY_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

PROXY_LOG="${GRC_PROXY_LOG:-/tmp/grc_patch_proxy.log}"
if [[ "${GRC_START_PROXY:-1}" == "1" ]]; then
  grc serve --config "${CONFIG_PATH}" --rules-dir "${RULES_DIR}" --trace-dir "${TRACE_DIR}" --port "${PORT}" >"${PROXY_LOG}" 2>&1 &
  PROXY_PID=$!
  if ! grc_wait_proxy_healthy "${PORT}" "${PROXY_LOG}"; then
    exit 1
  fi
fi

GENERATE_ARGS=(generate --model "${BFCL_MODEL}" --skip-server-setup --num-threads "${GRC_BFCL_NUM_THREADS}" --result-dir "${BFCL_RESULT_DIR}" --allow-overwrite)
EVAL_ARGS=(evaluate --model "${BFCL_MODEL}" --result-dir "${BFCL_RESULT_DIR}" --score-dir "${BFCL_SCORE_DIR}")
if [[ "${GRC_BFCL_USE_RUN_IDS:-0}" == "1" ]]; then
  GENERATE_ARGS+=(--run-ids)
fi
if [[ -n "${TEST_CATEGORY}" ]]; then
  GENERATE_ARGS+=(--test-category "${TEST_CATEGORY}")
  EVAL_ARGS+=(--test-category "${TEST_CATEGORY}")
fi
if [[ "${GRC_BFCL_PARTIAL_EVAL}" == "1" ]]; then
  EVAL_ARGS+=(--partial-eval)
fi

"${BFCL_CLI[@]}" "${GENERATE_ARGS[@]}"
bfcl_fix_result_layout "${BFCL_ROOT}"
"${BFCL_CLI[@]}" "${EVAL_ARGS[@]}"

AGGREGATE_ARGS=(--bfcl-root "${BFCL_ROOT}" --trace-dir "${TRACE_DIR}" --out "${ARTIFACT_DIR}/metrics.json" --repairs-out "${ARTIFACT_DIR}/repairs.jsonl" --failure-summary-out "${ARTIFACT_DIR}/failure_summary.json" --label "candidate" --protocol-id "${GRC_PROTOCOL_ID}" --model "${BFCL_MODEL}" --test-category "${TEST_CATEGORY}")
if [[ -n "${BASELINE_METRICS}" ]]; then
  AGGREGATE_ARGS+=(--baseline-metrics "${BASELINE_METRICS}")
fi
python "${REPO_ROOT}/scripts/aggregate_bfcl_metrics.py" "${AGGREGATE_ARGS[@]}"

write_run_manifest "${ARTIFACT_DIR}/run_manifest.json" "${RULES_DIR}" "${RULE_PATH}" "${RUN_ID}"
