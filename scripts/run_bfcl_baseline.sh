#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BFCL_MODEL="${1:-}"
TEST_CATEGORY="${2:-}"
RUN_ROOT="${3:-${REPO_ROOT}/outputs/bfcl/baseline}"
PORT="${4:-8011}"

bash "${REPO_ROOT}/scripts/run_bfcl_v4_baseline.sh" \
  "${BFCL_MODEL}" \
  "${RUN_ROOT}" \
  "${PORT}" \
  "${TEST_CATEGORY}"
