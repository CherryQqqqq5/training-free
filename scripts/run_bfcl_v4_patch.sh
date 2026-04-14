#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${REPO_ROOT}/configs/bfcl_v4_phase1.env"

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
  if [[ -f "${log_path}" ]]; then
    tail -n 80 "${log_path}" >&2 || true
  fi
  return 1
}

MODEL_NAME="${1:-${GRC_UPSTREAM_MODEL}}"
RUN_ROOT="${2:-${REPO_ROOT}/outputs/bfcl_v4/patch}"
PORT="${3:-8012}"
TEST_CATEGORY="${4:-${GRC_BFCL_TEST_CATEGORY}}"
CONFIG_PATH="${5:-${REPO_ROOT}/configs/runtime.yaml}"
RULES_DIR="${6:-${REPO_ROOT}/rules/active}"
TRACE_DIR="${7:-${RUN_ROOT}/traces}"
ARTIFACT_DIR="${8:-${RUN_ROOT}/artifacts}"
BASELINE_METRICS="${9:-}"
BFCL_ROOT="${RUN_ROOT}/bfcl"

mkdir -p "${BFCL_ROOT}" "${TRACE_DIR}" "${ARTIFACT_DIR}"
export BFCL_PROJECT_ROOT="${BFCL_ROOT}"
export LOCAL_SERVER_ENDPOINT=http://127.0.0.1
export LOCAL_SERVER_PORT="${PORT}"
export OPENAI_BASE_URL="http://127.0.0.1:${PORT}/v1"
export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"

PROXY_PID=""
cleanup() {
  if [[ -n "${PROXY_PID}" ]]; then
    kill "${PROXY_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

PROXY_LOG="${GRC_PROXY_LOG:-/tmp/grc_patch_proxy.log}"
if [[ "${GRC_START_PROXY:-1}" == "1" ]]; then
  grc serve \
    --config "${CONFIG_PATH}" \
    --rules-dir "${RULES_DIR}" \
    --trace-dir "${TRACE_DIR}" \
    --port "${PORT}" \
    >"${PROXY_LOG}" 2>&1 &
  PROXY_PID=$!
  if ! grc_wait_proxy_healthy "${PORT}" "${PROXY_LOG}"; then
    exit 1
  fi
  if ! kill -0 "${PROXY_PID}" 2>/dev/null; then
    echo "error: grc serve process exited before inference (pid ${PROXY_PID})" >&2
    exit 1
  fi
fi

GENERATE_ARGS=(generate --model "${MODEL_NAME}" --skip-server-setup --num-threads "${GRC_BFCL_NUM_THREADS}")
EVAL_ARGS=(evaluate --model "${MODEL_NAME}")
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

bfcl "${GENERATE_ARGS[@]}"
bfcl "${EVAL_ARGS[@]}"

AGGREGATE_ARGS=(
  --bfcl-root "${BFCL_ROOT}"
  --trace-dir "${TRACE_DIR}"
  --out "${ARTIFACT_DIR}/metrics.json"
  --repairs-out "${ARTIFACT_DIR}/repairs.jsonl"
  --failure-summary-out "${ARTIFACT_DIR}/failure_summary.json"
  --label "candidate"
  --protocol-id "${GRC_PROTOCOL_ID}"
  --model "${MODEL_NAME}"
  --test-category "${TEST_CATEGORY}"
)
if [[ -n "${BASELINE_METRICS}" ]]; then
  AGGREGATE_ARGS+=(--baseline-metrics "${BASELINE_METRICS}")
fi

python "${REPO_ROOT}/scripts/aggregate_bfcl_metrics.py" "${AGGREGATE_ARGS[@]}"
