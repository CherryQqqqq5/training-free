#!/usr/bin/env bash
# Initialize BFCL_PROJECT_ROOT with .env and optional test_case_ids (no venv).
# Use this when dependencies are already installed (e.g. conda env `tf`).
# The BFCL runners will rewrite connection-related .env keys per run so the
# fixture stays aligned with the local proxy endpoint and port.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BFCL_ROOT="${1:-${REPO_ROOT}/outputs/bfcl_v4/baseline/bfcl}"

mkdir -p "${BFCL_ROOT}"

python <<PY
import pathlib
import shutil

import bfcl_eval

root = pathlib.Path(bfcl_eval.__path__[0])
dst = pathlib.Path("${BFCL_ROOT}")
dst.mkdir(parents=True, exist_ok=True)
shutil.copy(root / ".env.example", dst / ".env")
example = root / "test_case_ids_to_generate.json.example"
if example.exists():
    shutil.copy(example, dst / "test_case_ids_to_generate.json")
print(f"Wrote BFCL fixture: {dst}/.env")
PY
