#!/usr/bin/env bash
set -euo pipefail

TRACE_DIR="${1:-outputs/traces/baseline}"
FAILURES_OUT="${2:-outputs/reports/failures.jsonl}"
PATCH_OUT="${3:-rules/candidates/patch_auto_001/rule.yaml}"
PATCH_ID="${4:-patch_auto_001}"
export GRC_CANDIDATE_DIR="${5:-rules/candidates/${PATCH_ID}}"

grc mine --trace-dir "${TRACE_DIR}" --out "${FAILURES_OUT}"
grc compile --failures "${FAILURES_OUT}" --out "${PATCH_OUT}" --patch-id "${PATCH_ID}" --candidate-dir "${GRC_CANDIDATE_DIR}"
