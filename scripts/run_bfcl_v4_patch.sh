#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${REPO_ROOT}/configs/bfcl_v4_phase1.env"
if [[ -f "${REPO_ROOT}/configs/bfcl_v4_openrouter.env" ]]; then
  source "${REPO_ROOT}/configs/bfcl_v4_openrouter.env"
fi

BFCL_RUNTIME_CONFIG_DEFAULT="${GRC_BFCL_RUNTIME_CONFIG:-${REPO_ROOT}/configs/runtime_bfcl_structured.yaml}"
BFCL_PREFLIGHT_DEFAULT="${GRC_BFCL_PREFLIGHT:-1}"

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

bfcl_fix_result_layout() {
  local bfcl_root="$1"
  local nested_result_dir="${bfcl_root}/${bfcl_root}/result"
  local canonical_result_dir="${bfcl_root}/result"
  if [[ ! -d "${nested_result_dir}" ]]; then
    return 0
  fi
  mkdir -p "${canonical_result_dir}"
  cp -R "${nested_result_dir}/." "${canonical_result_dir}/"
  echo "fixed bfcl result layout: ${nested_result_dir} -> ${canonical_result_dir}" >&2
}

BFCL_CLI=(python "${REPO_ROOT}/scripts/run_bfcl_cli.py")

validate_model_split() {
  if [[ -z "${BFCL_MODEL}" ]]; then
    echo "error: BFCL model alias is empty; set GRC_BFCL_MODEL or pass it as arg1" >&2
    exit 2
  fi
  if [[ "${GRC_UPSTREAM_PROFILE:-}" == "openrouter" && "${GRC_UPSTREAM_MODEL:-}" == *-FC ]]; then
    echo "error: GRC_UPSTREAM_MODEL=${GRC_UPSTREAM_MODEL} looks like a BFCL alias, not an OpenRouter model route" >&2
    echo "       use GRC_BFCL_MODEL=${BFCL_MODEL} for bfcl --model and set GRC_UPSTREAM_MODEL to an OpenRouter route such as x-ai/grok-3-beta" >&2
    exit 2
  fi
}

ensure_upstream_auth() {
  case "${GRC_UPSTREAM_PROFILE:-}" in
    openrouter)
      if [[ -z "${OPENROUTER_API_KEY:-}" && -n "${OPENAI_API_KEY:-}" && "${OPENAI_API_KEY}" != "dummy" ]]; then
        export OPENROUTER_API_KEY="${OPENAI_API_KEY}"
      fi
      if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
        if [[ "${BFCL_PREFLIGHT_DEFAULT}" == "1" ]]; then
          python - "${ARTIFACT_DIR}/preflight_report.json" <<'PY'
import json
import sys
from pathlib import Path

out_path = Path(sys.argv[1])
out_path.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "base_url": None,
    "config_path": None,
    "trace_dir": None,
    "expected_api_key_env": "OPENROUTER_API_KEY",
    "environment_check": {
        "expected_api_key_env": "OPENROUTER_API_KEY",
        "is_set": False,
        "reason": "required upstream env var is unset: OPENROUTER_API_KEY",
    },
    "checks": [],
    "passed": False,
}
out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
PY
        fi
        echo "error: GRC_UPSTREAM_PROFILE=openrouter but OPENROUTER_API_KEY is unset" >&2
        echo "       set OPENROUTER_API_KEY, or source configs/bfcl_v4_openrouter.env before running BFCL" >&2
        exit 2
      fi
      ;;
  esac
}

clean_run_state() {
  if [[ "${GRC_BFCL_CLEAN_RUN:-1}" != "1" ]]; then
    return 0
  fi
  rm -rf \
    "${BFCL_ROOT}/result" \
    "${BFCL_ROOT}/score" \
    "${BFCL_ROOT:?}/${BFCL_ROOT#/}/result" \
    "${TRACE_DIR}"
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
BFCL_ROOT="${RUN_ROOT}/bfcl"
BFCL_RESULT_DIR="${BFCL_ROOT}/result"
BFCL_SCORE_DIR="${BFCL_ROOT}/score"
RUN_ID="${GRC_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"

validate_model_split
ensure_upstream_auth
clean_run_state

mkdir -p "${BFCL_ROOT}" "${TRACE_DIR}" "${ARTIFACT_DIR}"
export BFCL_PROJECT_ROOT="${BFCL_ROOT}"
export LOCAL_SERVER_ENDPOINT=http://127.0.0.1
export LOCAL_SERVER_PORT="${PORT}"
export OPENAI_BASE_URL="http://127.0.0.1:${PORT}/v1"
export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"

python "${REPO_ROOT}/scripts/sync_bfcl_fixture_env.py" \
  --bfcl-root "${BFCL_ROOT}" \
  --openai-base-url "${OPENAI_BASE_URL}" \
  --local-server-endpoint "${LOCAL_SERVER_ENDPOINT}" \
  --local-server-port "${LOCAL_SERVER_PORT}" \
  --openai-api-key "${OPENAI_API_KEY}"

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

if [[ "${BFCL_PREFLIGHT_DEFAULT}" == "1" ]]; then
  python "${REPO_ROOT}/scripts/run_bfcl_preflight.py" \
    --base-url "http://127.0.0.1:${PORT}" \
    --trace-dir "${TRACE_DIR}" \
    --config-path "${CONFIG_PATH}" \
    --out "${ARTIFACT_DIR}/preflight_report.json"
fi

GENERATE_ARGS=(
  generate
  --model "${BFCL_MODEL}"
  --skip-server-setup
  --num-threads "${GRC_BFCL_NUM_THREADS}"
  --result-dir "${BFCL_RESULT_DIR}"
  --allow-overwrite
)
EVAL_ARGS=(
  evaluate
  --model "${BFCL_MODEL}"
  --result-dir "${BFCL_RESULT_DIR}"
  --score-dir "${BFCL_SCORE_DIR}"
)
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

AGGREGATE_ARGS=(
  --bfcl-root "${BFCL_ROOT}"
  --trace-dir "${TRACE_DIR}"
  --out "${ARTIFACT_DIR}/metrics.json"
  --repairs-out "${ARTIFACT_DIR}/repairs.jsonl"
  --failure-summary-out "${ARTIFACT_DIR}/failure_summary.json"
  --label "candidate"
  --protocol-id "${GRC_PROTOCOL_ID}"
  --model "${BFCL_MODEL}"
  --test-category "${TEST_CATEGORY}"
)
if [[ -n "${BASELINE_METRICS}" ]]; then
  AGGREGATE_ARGS+=(--baseline-metrics "${BASELINE_METRICS}")
fi

python "${REPO_ROOT}/scripts/aggregate_bfcl_metrics.py" "${AGGREGATE_ARGS[@]}"

RULE_PATH=""
if [[ -f "${RULES_DIR}/rule.yaml" ]]; then
  RULE_PATH="${RULES_DIR}/rule.yaml"
fi

MANIFEST_ARGS=(
  --out "${ARTIFACT_DIR}/run_manifest.json"
  --kind candidate
  --repo-root "${REPO_ROOT}"
  --runtime-config-path "${CONFIG_PATH}"
  --rules-dir "${RULES_DIR}"
  --bfcl-model-alias "${BFCL_MODEL}"
  --protocol-id "${GRC_PROTOCOL_ID}"
  --test-category "${TEST_CATEGORY}"
  --run-id "${RUN_ID}"
)
if [[ -n "${RULE_PATH}" ]]; then
  MANIFEST_ARGS+=(--rule-path "${RULE_PATH}")
fi

python "${REPO_ROOT}/scripts/write_run_manifest.py" "${MANIFEST_ARGS[@]}"
