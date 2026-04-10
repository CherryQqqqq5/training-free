#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate

pip install -U pip
pip install "bfcl-eval==2025.12.17"

export BFCL_PROJECT_ROOT="${PWD}/outputs/bfcl_v4/baseline/bfcl"
mkdir -p "${BFCL_PROJECT_ROOT}"

cp "$(python -c "import bfcl_eval, pathlib; print(pathlib.Path(bfcl_eval.__path__[0]) / '.env.example')")" \
  "${BFCL_PROJECT_ROOT}/.env"

cp "$(python -c "import bfcl_eval, pathlib; print(pathlib.Path(bfcl_eval.__path__[0]) / 'test_case_ids_to_generate.json.example')")" \
  "${BFCL_PROJECT_ROOT}/test_case_ids_to_generate.json"

echo "BFCL installed into .venv"
echo "Pinned evaluator: bfcl-eval==2025.12.17"
echo "Reference checkout: f7cf735"
echo "BFCL_PROJECT_ROOT=${BFCL_PROJECT_ROOT}"
