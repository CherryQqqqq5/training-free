#!/usr/bin/env bash
set -euo pipefail

MODEL_NAME="${1:-gpt-4o-2024-11-20-FC}"
TEST_CATEGORY="${2:-simple,parallel,live_multiple,multi_turn_base}"
ROOT="${3:-$PWD/outputs/bfcl/baseline}"
PORT="${4:-8011}"

export BFCL_PROJECT_ROOT="${ROOT}"
mkdir -p "${BFCL_PROJECT_ROOT}"

export LOCAL_SERVER_ENDPOINT=127.0.0.1
export LOCAL_SERVER_PORT="${PORT}"

bfcl generate \
  --model "${MODEL_NAME}" \
  --test-category "${TEST_CATEGORY}" \
  --run-ids \
  --skip-server-setup \
  --num-threads 1

bfcl evaluate \
  --model "${MODEL_NAME}" \
  --test-category "${TEST_CATEGORY}" \
  --partial-eval

