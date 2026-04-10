#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${REPO_ROOT}/configs/bfcl_v4_phase1.env"

RUN_ID="${1:-$(date +%Y%m%d_%H%M%S)}"
PATCH_ID="${2:-patch_${RUN_ID}}"
TEST_CATEGORY="${3:-${GRC_BFCL_TEST_CATEGORY}}"
MODEL_NAME="${4:-${GRC_UPSTREAM_MODEL}}"

BASELINE_ROOT="${REPO_ROOT}/outputs/bfcl_v4/baseline/${RUN_ID}"
PATCH_ROOT="${REPO_ROOT}/outputs/bfcl_v4/patch/${RUN_ID}"
FAILURES_OUT="${REPO_ROOT}/outputs/reports/${RUN_ID}_failures.jsonl"
CANDIDATE_DIR="${REPO_ROOT}/rules/candidates/${PATCH_ID}"
RULE_PATH="${CANDIDATE_DIR}/rule.yaml"
BASELINE_METRICS="${BASELINE_ROOT}/artifacts/metrics.json"
CANDIDATE_METRICS="${CANDIDATE_DIR}/metrics.json"

mkdir -p "${REPO_ROOT}/rules/candidates" "${REPO_ROOT}/rules/accepted" "${REPO_ROOT}/rules/rejected" "${REPO_ROOT}/rules/active"

bash "${REPO_ROOT}/scripts/run_bfcl_v4_baseline.sh" \
  "${MODEL_NAME}" \
  "${BASELINE_ROOT}" \
  "8011" \
  "${TEST_CATEGORY}" \
  "${REPO_ROOT}/configs/runtime.yaml" \
  "${REPO_ROOT}/rules/baseline_empty" \
  "${BASELINE_ROOT}/traces" \
  "${BASELINE_ROOT}/artifacts"

grc mine --trace-dir "${BASELINE_ROOT}/traces" --out "${FAILURES_OUT}"
grc compile \
  --failures "${FAILURES_OUT}" \
  --out "${RULE_PATH}" \
  --patch-id "${PATCH_ID}" \
  --candidate-dir "${CANDIDATE_DIR}"

bash "${REPO_ROOT}/scripts/run_bfcl_v4_patch.sh" \
  "${MODEL_NAME}" \
  "${PATCH_ROOT}" \
  "8012" \
  "${TEST_CATEGORY}" \
  "${REPO_ROOT}/configs/runtime.yaml" \
  "${CANDIDATE_DIR}" \
  "${PATCH_ROOT}/traces" \
  "${CANDIDATE_DIR}" \
  "${BASELINE_METRICS}"

grc select \
  --baseline-metrics "${BASELINE_METRICS}" \
  --candidate-metrics "${CANDIDATE_METRICS}" \
  --candidate-dir "${CANDIDATE_DIR}" \
  --rule-path "${RULE_PATH}" \
  --accepted-dir "${REPO_ROOT}/rules/accepted" \
  --rejected-dir "${REPO_ROOT}/rules/rejected" \
  --active-dir "${REPO_ROOT}/rules/active" \
  --out "${CANDIDATE_DIR}/accept.json"
