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
    "lane": "compatibility_baseline",
    "source": "bfcl_adapter",
    "git_sha": git_sha,
    "git_dirty": git_dirty == "true",
    "runtime_config_path": os.environ.get("CONFIG_PATH", ""),
    "rules_dir": rules_dir,
    "rule_path": rule_path or None,
    "run_id": run_id,
    "timestamp": datetime.now(timezone.utc).isoformat(),
}
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(manifest, handle, ensure_ascii=False, indent=2)
PY
}

BFCL_CLI=(python "${REPO_ROOT}/scripts/run_bfcl_cli.py")

validate_model_split() {
  if [[ -z "${BFCL_MODEL}" ]]; then
    echo "error: BFCL model alias is empty; set GRC_BFCL_MODEL or pass it as arg1" >&2
    exit 2
  fi
}

clean_run_state() {
  if [[ "${GRC_BFCL_CLEAN_RUN:-1}" != "1" ]]; then
    return 0
  fi
  rm -rf "${BFCL_ROOT}/result" "${BFCL_ROOT}/score" "${BFCL_ROOT:?}/${BFCL_ROOT#/}/result" "${TRACE_DIR}"
}

BFCL_MODEL="${1:-${GRC_BFCL_MODEL}}"
RUN_ROOT="${2:-${REPO_ROOT}/outputs/bfcl_v4/baseline}"
PORT="${3:-8011}"
TEST_CATEGORY="${4:-${GRC_BFCL_TEST_CATEGORY}}"
CONFIG_PATH="${5:-${BFCL_RUNTIME_CONFIG_DEFAULT}}"
RULES_DIR="${6:-${REPO_ROOT}/rules/baseline_empty}"
TRACE_DIR="${7:-${RUN_ROOT}/traces}"
ARTIFACT_DIR="${8:-${RUN_ROOT}/artifacts}"
RUN_ID="${9:-baseline_${TEST_CATEGORY:-all}}"
BFCL_ROOT="${RUN_ROOT}/bfcl"
BFCL_RESULT_DIR="${BFCL_ROOT}/result"
BFCL_SCORE_DIR="${BFCL_ROOT}/score"

validate_model_split
clean_run_state

mkdir -p "${BFCL_ROOT}" "${TRACE_DIR}" "${ARTIFACT_DIR}"
mkdir -p "${RULES_DIR}"

# Restore baseline rules dir guard (experiment hygiene - prevent accidental pollution of compatibility baseline)
if [[ "${GRC_ALLOW_DIRTY_BASELINE_RULES:-0}" != "1" ]]; then
  mapfile -t BASELINE_RULE_FILES < <(find "${RULES_DIR}" -maxdepth 1 -type f -name '*.yaml' | sort)
  if [[ "${#BASELINE_RULE_FILES[@]}" -gt 0 ]]; then
    echo "baseline rules dir must be empty of YAML patches: ${RULES_DIR}" >&2
    printf 'found baseline rule files:\n' >&2
    printf '  %s\n' "${BASELINE_RULE_FILES[@]}" >&2
    exit 1
  fi
fi

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

PROXY_LOG="${GRC_PROXY_LOG:-/tmp/grc_baseline_proxy.log}"
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

python "${REPO_ROOT}/scripts/aggregate_bfcl_metrics.py" --bfcl-root "${BFCL_ROOT}" --trace-dir "${TRACE_DIR}" --out "${ARTIFACT_DIR}/metrics.json" --repairs-out "${ARTIFACT_DIR}/repairs.jsonl" --failure-summary-out "${ARTIFACT_DIR}/failure_summary.json" --label "baseline" --protocol-id "${GRC_PROTOCOL_ID}" --model "${BFCL_MODEL}" --test-category "${TEST_CATEGORY}"

write_run_manifest "${ARTIFACT_DIR}/run_manifest.json" "${RULES_DIR}" "" "${RUN_ID}"
