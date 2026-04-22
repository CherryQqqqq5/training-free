#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${REPO_ROOT}/configs/bfcl_v4_phase1.env"
BFCL_RUNTIME_CONFIG_DEFAULT="${GRC_BFCL_RUNTIME_CONFIG:-${REPO_ROOT}/configs/runtime_bfcl_structured.yaml}"

RUN_ID="${1:-$(date +%Y%m%d_%H%M%S)}"
PATCH_ID="${2:-patch_${RUN_ID}}"
TEST_CATEGORY="${3:-${GRC_BFCL_TEST_CATEGORY}}"
BFCL_MODEL="${4:-${GRC_BFCL_MODEL}}"

BASELINE_ROOT="${REPO_ROOT}/outputs/bfcl_v4/baseline/${RUN_ID}"
PATCH_ROOT="${REPO_ROOT}/outputs/bfcl_v4/patch/${RUN_ID}"
FAILURES_OUT="${REPO_ROOT}/outputs/reports/${RUN_ID}_failures.jsonl"
CANDIDATE_DIR="${REPO_ROOT}/rules/candidates/${PATCH_ID}"
RULE_PATH="${CANDIDATE_DIR}/rule.yaml"
COMPILE_STATUS_PATH="${CANDIDATE_DIR}/compile_status.json"
NO_CANDIDATE_PATH="${CANDIDATE_DIR}/no_candidate.json"
EVALUATION_INCOMPLETE_PATH="${CANDIDATE_DIR}/evaluation_incomplete.json"
BASELINE_METRICS="${BASELINE_ROOT}/artifacts/metrics.json"
CANDIDATE_METRICS="${CANDIDATE_DIR}/metrics.json"
PAIRED_RERUN_PATH="${CANDIDATE_DIR}/paired_rerun.json"
PAIRED_RERUN_ENABLED="${GRC_BFCL_PAIRED_RERUN:-1}"

mkdir -p "${REPO_ROOT}/rules/candidates" "${REPO_ROOT}/rules/accepted" "${REPO_ROOT}/rules/rejected" "${REPO_ROOT}/rules/active"
export GRC_RUN_ID="${RUN_ID}"

bash "${REPO_ROOT}/scripts/run_bfcl_v4_baseline.sh" \
  "${BFCL_MODEL}" \
  "${BASELINE_ROOT}" \
  "8011" \
  "${TEST_CATEGORY}" \
  "${BFCL_RUNTIME_CONFIG_DEFAULT}" \
  "${REPO_ROOT}/rules/baseline_empty" \
  "${BASELINE_ROOT}/traces" \
  "${BASELINE_ROOT}/artifacts"

grc mine --trace-dir "${BASELINE_ROOT}/traces" --out "${FAILURES_OUT}"
if ! grc compile \
  --failures "${FAILURES_OUT}" \
  --out "${RULE_PATH}" \
  --patch-id "${PATCH_ID}" \
  --candidate-dir "${CANDIDATE_DIR}"; then
  echo "compile returned non-zero; inspecting compile_status.json"
fi

COMPILE_STATUS="$(python -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("status",""))' "${COMPILE_STATUS_PATH}")"
if [[ "${COMPILE_STATUS}" != "actionable_patch" ]]; then
  python -c 'import json,sys; status=json.load(open(sys.argv[1],"r",encoding="utf-8")); out={"decision_code": status.get("status"), "reason": status.get("reason"), "compile_status": status}; json.dump(out, open(sys.argv[2],"w",encoding="utf-8"), ensure_ascii=False, indent=2)' \
    "${COMPILE_STATUS_PATH}" "${NO_CANDIDATE_PATH}"
  echo "skipped patch benchmark: ${COMPILE_STATUS}"
  exit 0
fi

bash "${REPO_ROOT}/scripts/run_bfcl_v4_patch.sh" \
  "${BFCL_MODEL}" \
  "${PATCH_ROOT}" \
  "8012" \
  "${TEST_CATEGORY}" \
  "${BFCL_RUNTIME_CONFIG_DEFAULT}" \
  "${CANDIDATE_DIR}" \
  "${PATCH_ROOT}/traces" \
  "${CANDIDATE_DIR}" \
  "${BASELINE_METRICS}"

EVALUATION_STATUS="$(python -c 'import json,sys; print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("evaluation_status",""))' "${CANDIDATE_METRICS}")"
if [[ "${EVALUATION_STATUS}" != "complete" ]]; then
  python -c 'import json,sys; metrics=json.load(open(sys.argv[1],"r",encoding="utf-8")); out={"decision_code":"evaluation_incomplete","reason":"candidate evaluation artifacts are incomplete","metrics":metrics}; json.dump(out, open(sys.argv[2],"w",encoding="utf-8"), ensure_ascii=False, indent=2)' \
    "${CANDIDATE_METRICS}" "${EVALUATION_INCOMPLETE_PATH}"
  echo "skipped select: ${EVALUATION_STATUS}"
  exit 0
fi

if [[ "${PAIRED_RERUN_ENABLED}" == "1" ]]; then
  RERUN_ROOT="${PATCH_ROOT}_rerun"
  RERUN_ARTIFACT_DIR="${CANDIDATE_DIR}/rerun"
  export GRC_RUN_ID="${RUN_ID}_rerun"
  bash "${REPO_ROOT}/scripts/run_bfcl_v4_patch.sh" \
    "${BFCL_MODEL}" \
    "${RERUN_ROOT}" \
    "8013" \
    "${TEST_CATEGORY}" \
    "${BFCL_RUNTIME_CONFIG_DEFAULT}" \
    "${CANDIDATE_DIR}" \
    "${RERUN_ROOT}/traces" \
    "${RERUN_ARTIFACT_DIR}" \
    "${BASELINE_METRICS}"
  export GRC_RUN_ID="${RUN_ID}"
  python "${REPO_ROOT}/scripts/assess_paired_rerun.py" \
    --baseline "${BASELINE_METRICS}" \
    --primary "${CANDIDATE_METRICS}" \
    --rerun "${RERUN_ARTIFACT_DIR}/metrics.json" \
    --out "${PAIRED_RERUN_PATH}"
fi

grc select \
  --baseline-metrics "${BASELINE_METRICS}" \
  --candidate-metrics "${CANDIDATE_METRICS}" \
  --candidate-dir "${CANDIDATE_DIR}" \
  --rule-path "${RULE_PATH}" \
  --accepted-dir "${REPO_ROOT}/rules/accepted" \
  --rejected-dir "${REPO_ROOT}/rules/rejected" \
  --active-dir "${REPO_ROOT}/rules/active" \
  --out "${CANDIDATE_DIR}/accept.json"
