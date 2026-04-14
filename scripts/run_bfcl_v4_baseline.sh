#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${REPO_ROOT}/configs/bfcl_v4_phase1.env"

# BFCL's OpenAI client reads OPENAI_BASE_URL; bfcl_eval's .env often pins 8011. Always align with
# the port this script binds for the local grc proxy so patch runs (8012) are not sent to a dead 8011.
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
RUN_ROOT="${2:-${REPO_ROOT}/outputs/bfcl_v4/baseline}"
PORT="${3:-8011}"
TEST_CATEGORY="${4:-${GRC_BFCL_TEST_CATEGORY}}"
CONFIG_PATH="${5:-${REPO_ROOT}/configs/runtime.yaml}"
RULES_DIR="${6:-${REPO_ROOT}/rules/baseline_empty}"
TRACE_DIR="${7:-${RUN_ROOT}/traces}"
ARTIFACT_DIR="${8:-${RUN_ROOT}/artifacts}"
BFCL_ROOT="${RUN_ROOT}/bfcl"

mkdir -p "${BFCL_ROOT}" "${TRACE_DIR}" "${ARTIFACT_DIR}"
mkdir -p "${RULES_DIR}"

if [[ "${GRC_ALLOW_DIRTY_BASELINE_RULES:-0}" != "1" ]]; then
  mapfile -t BASELINE_RULE_FILES < <(find "${RULES_DIR}" -maxdepth 1 -type f -name '*.yaml' | sort)
  if [[ "${#BASELINE_RULE_FILES[@]}" -gt 0 ]]; then
    echo "baseline rules dir must be empty of YAML patches: ${RULES_DIR}" >&2
    printf 'found baseline rule files:\n' >&2
    printf '  %s\n' "${BASELINE_RULE_FILES[@]}" >&2
    exit 1
  fi
fi

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

PROXY_LOG="${GRC_PROXY_LOG:-/tmp/grc_baseline_proxy.log}"
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
