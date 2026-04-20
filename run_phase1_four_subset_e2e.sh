#!/usr/bin/env bash
# Phase-1 closed loop: baseline -> mine -> compile -> patch run -> select, for four BFCL categories.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
if [[ -d "${REPO_ROOT}/scripts" ]]; then
  source "${REPO_ROOT}/configs/bfcl_v4_phase1.env"
else
  REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
  source "${REPO_ROOT}/configs/bfcl_v4_phase1.env"
fi

BFCL_RUNTIME_CONFIG_DEFAULT="${GRC_BFCL_RUNTIME_CONFIG:-${REPO_ROOT}/configs/runtime_bfcl_structured.yaml}"
if [[ -f "${REPO_ROOT}/configs/bfcl_v4_openrouter.env" ]]; then
  source "${REPO_ROOT}/configs/bfcl_v4_openrouter.env"
fi

BFCL_MODEL="${1:-${GRC_BFCL_MODEL}}"
RUN_ID="${2:-phase1_four}"
CATEGORIES=(simple_python multiple parallel_multiple multi_turn_miss_param)

mkdir -p "${REPO_ROOT}/rules/candidates" "${REPO_ROOT}/rules/accepted" "${REPO_ROOT}/rules/rejected" "${REPO_ROOT}/rules/active" "${REPO_ROOT}/outputs/reports"

for CAT in "${CATEGORIES[@]}"; do
  echo
  echo "==================== ${CAT} ===================="

  BASELINE_ROOT="${REPO_ROOT}/outputs/bfcl_v4/baseline/${CAT}"
  PATCH_ROOT="${REPO_ROOT}/outputs/bfcl_v4/patch/${CAT}"
  FAILURES_OUT="${REPO_ROOT}/outputs/reports/${RUN_ID}_${CAT}_failures.jsonl"
  PATCH_ID="${RUN_ID}_${CAT}"
  CANDIDATE_DIR="${REPO_ROOT}/rules/candidates/${PATCH_ID}"
  RULE_PATH="${CANDIDATE_DIR}/rule.yaml"
  COMPILE_STATUS_PATH="${CANDIDATE_DIR}/compile_status.json"
  BASELINE_METRICS="${BASELINE_ROOT}/artifacts/metrics.json"
  CANDIDATE_METRICS="${CANDIDATE_DIR}/metrics.json"
  BASELINE_MANIFEST="${BASELINE_ROOT}/artifacts/run_manifest.json"
  CANDIDATE_MANIFEST="${CANDIDATE_DIR}/run_manifest.json"

  bash "${REPO_ROOT}/scripts/run_bfcl_v4_baseline.sh"     "${BFCL_MODEL}"     "${BASELINE_ROOT}"     "8011"     "${CAT}"     "${BFCL_RUNTIME_CONFIG_DEFAULT}"     "${REPO_ROOT}/rules/baseline_empty"     "${BASELINE_ROOT}/traces"     "${BASELINE_ROOT}/artifacts"     "${RUN_ID}_baseline_${CAT}"

  grc mine --trace-dir "${BASELINE_ROOT}/traces" --out "${FAILURES_OUT}"
  grc compile --failures "${FAILURES_OUT}" --out "${RULE_PATH}" --patch-id "${PATCH_ID}" --candidate-dir "${CANDIDATE_DIR}"

  COMPILE_STATUS="$(python3 - "${COMPILE_STATUS_PATH}" <<"PY"
import json, sys
try:
    print(json.loads(open(sys.argv[1], encoding="utf-8").read()).get("status", "compile_failed"))
except Exception:
    print("compile_failed")
PY
)"

  if [[ "${COMPILE_STATUS}" != "actionable_patch" ]]; then
    python3 - "${CANDIDATE_DIR}/no_candidate.json" "${COMPILE_STATUS}" "${COMPILE_STATUS_PATH}" <<"PY"
import json, sys
out_path, reason, status_path = sys.argv[1:4]
status_payload = {}
try:
    status_payload = json.loads(open(status_path, encoding="utf-8").read())
except Exception:
    pass
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump({"stop_reason": reason, "compile_status": status_payload}, handle, ensure_ascii=False, indent=2)
PY
    echo "skip patch benchmark due to compile status: ${COMPILE_STATUS}"
    continue
  fi

  bash "${REPO_ROOT}/scripts/run_bfcl_v4_patch.sh"     "${BFCL_MODEL}"     "${PATCH_ROOT}"     "8012"     "${CAT}"     "${BFCL_RUNTIME_CONFIG_DEFAULT}"     "${CANDIDATE_DIR}"     "${PATCH_ROOT}/traces"     "${CANDIDATE_DIR}"     "${BASELINE_METRICS}"     "${RULE_PATH}"     "${RUN_ID}_candidate_${CAT}"

  EVAL_STATUS="$(python3 - "${CANDIDATE_METRICS}" <<"PY"
import json, sys
try:
    print(json.loads(open(sys.argv[1], encoding="utf-8").read()).get("evaluation_status", "incomplete"))
except Exception:
    print("incomplete")
PY
)"

  if [[ "${EVAL_STATUS}" != "complete" ]]; then
    python3 - "${CANDIDATE_DIR}/evaluation_incomplete.json" "${CANDIDATE_METRICS}" <<"PY"
import json, sys
out_path, metrics_path = sys.argv[1:3]
payload = {"stop_reason": "evaluation_incomplete"}
try:
    payload["metrics"] = json.loads(open(metrics_path, encoding="utf-8").read())
except Exception as exc:
    payload["metrics_read_error"] = str(exc)
with open(out_path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2)
PY
    echo "skip select due to evaluation_status=${EVAL_STATUS}"
    continue
  fi

  grc select     --baseline-metrics "${BASELINE_METRICS}"     --candidate-metrics "${CANDIDATE_METRICS}"     --baseline-manifest "${BASELINE_MANIFEST}"     --candidate-manifest "${CANDIDATE_MANIFEST}"     --compile-status "${COMPILE_STATUS_PATH}"     --candidate-dir "${CANDIDATE_DIR}"     --rule-path "${RULE_PATH}"     --accepted-dir "${REPO_ROOT}/rules/accepted"     --rejected-dir "${REPO_ROOT}/rules/rejected"     --active-dir "${REPO_ROOT}/rules/active"     --out "${CANDIDATE_DIR}/accept.json"

  echo "done: ${CAT}"
done
