#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${REPO_ROOT}/configs/bfcl_v4_phase1.env"

MODEL_NAME="${1:-${GRC_UPSTREAM_MODEL}}"
RUN_ROOT="${2:-${REPO_ROOT}/outputs/bfcl_v4/baseline}"
PORT="${3:-8011}"
TEST_CATEGORY="${4:-${GRC_BFCL_TEST_CATEGORY}}"
CONFIG_PATH="${5:-${REPO_ROOT}/configs/runtime.yaml}"
RULES_DIR="${6:-${REPO_ROOT}/rules/active}"
TRACE_DIR="${7:-${RUN_ROOT}/traces}"
ARTIFACT_DIR="${8:-${RUN_ROOT}/artifacts}"
BFCL_ROOT="${RUN_ROOT}/bfcl"

mkdir -p "${BFCL_ROOT}" "${TRACE_DIR}" "${ARTIFACT_DIR}"
export BFCL_PROJECT_ROOT="${BFCL_ROOT}"
export LOCAL_SERVER_ENDPOINT=127.0.0.1
export LOCAL_SERVER_PORT="${PORT}"

PROXY_PID=""
cleanup() {
  if [[ -n "${PROXY_PID}" ]]; then
    kill "${PROXY_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ "${GRC_START_PROXY:-1}" == "1" ]]; then
  grc serve \
    --config "${CONFIG_PATH}" \
    --rules-dir "${RULES_DIR}" \
    --trace-dir "${TRACE_DIR}" \
    --port "${PORT}" \
    >/tmp/grc_baseline_proxy.log 2>&1 &
  PROXY_PID=$!

  for _ in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
      break
    fi
    sleep 1
  done
fi

GENERATE_ARGS=(generate --model "${MODEL_NAME}" --run-ids --skip-server-setup --num-threads "${GRC_BFCL_NUM_THREADS}")
EVAL_ARGS=(evaluate --model "${MODEL_NAME}")
if [[ -n "${TEST_CATEGORY}" ]]; then
  GENERATE_ARGS+=(--test-category "${TEST_CATEGORY}")
  EVAL_ARGS+=(--test-category "${TEST_CATEGORY}")
fi
if [[ "${GRC_BFCL_PARTIAL_EVAL}" == "1" ]]; then
  EVAL_ARGS+=(--partial-eval)
fi

bfcl "${GENERATE_ARGS[@]}"
bfcl "${EVAL_ARGS[@]}"

python "${REPO_ROOT}/scripts/aggregate_bfcl_metrics.py" \
  --bfcl-root "${BFCL_ROOT}" \
  --trace-dir "${TRACE_DIR}" \
  --out "${ARTIFACT_DIR}/metrics.json" \
  --repairs-out "${ARTIFACT_DIR}/repairs.jsonl" \
  --failure-summary-out "${ARTIFACT_DIR}/failure_summary.json" \
  --label "baseline" \
  --protocol-id "${GRC_PROTOCOL_ID}" \
  --model "${MODEL_NAME}" \
  --test-category "${TEST_CATEGORY}"
