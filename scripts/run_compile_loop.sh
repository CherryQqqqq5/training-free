#!/usr/bin/env bash
set -euo pipefail

TRACE_DIR="${1:-outputs/traces/baseline}"
FAILURES_OUT="${2:-outputs/reports/failures.jsonl}"
PATCH_OUT="${3:-rules/active/001_arg_repair.yaml}"

grc mine --trace-dir "${TRACE_DIR}" --out "${FAILURES_OUT}"
grc compile --failures "${FAILURES_OUT}" --out "${PATCH_OUT}"

