#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_ROOT"

# ===== Required env =====
: "${OPENROUTER_API_KEY:?OPENROUTER_API_KEY is required}"

# ===== Stable runtime env =====
export OPENAI_API_KEY="${OPENAI_API_KEY:-dummy}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-http://127.0.0.1:8011/v1}"

export GRC_UPSTREAM_PROFILE="${GRC_UPSTREAM_PROFILE:-openrouter}"
export GRC_UPSTREAM_BASE_URL="${GRC_UPSTREAM_BASE_URL:-https://openrouter.ai/api/v1}"
export GRC_UPSTREAM_MODEL="${GRC_UPSTREAM_MODEL:-x-ai/grok-3-beta}"
export OPENROUTER_HTTP_REFERER="${OPENROUTER_HTTP_REFERER:-https://github.com/CherryQqqqq5/training-free}"

MODEL_ALIAS="${MODEL_ALIAS:-openrouter__grok-3-beta}"
SUBSETS=("simple_python" "multiple" "parallel_multiple" "multi_turn_miss_param")

# ===== Ensure alias exists in bfcl_eval =====
python - <<'PY'
from pathlib import Path
import bfcl_eval.constants.model_config as mc
p = Path(mc.__file__)
s = p.read_text(encoding="utf-8")
needle = 'MODEL_CONFIG_MAPPING["openrouter__grok-3-beta"]'
if needle not in s:
    s += '\nMODEL_CONFIG_MAPPING["openrouter__grok-3-beta"] = MODEL_CONFIG_MAPPING["gpt-4o-2024-11-20"]\n'
    p.write_text(s, encoding="utf-8")
print("alias ready: openrouter__grok-3-beta")
PY

mkdir -p outputs/reports rules/candidates rules/accepted rules/rejected rules/active

run_one_subset () {
  local subset="$1"
  local base_root="outputs/bfcl_v4/baseline/${subset}"
  local patch_root="outputs/bfcl_v4/patch/${subset}"
  local failures_out="outputs/reports/${subset}_failures.jsonl"
  local patch_id="patch_${subset}_001"
  local cand_dir="rules/candidates/${patch_id}"
  local rule_path="${cand_dir}/rule.yaml"

  echo
  echo "==================== ${subset} ===================="

  # clean old run for reproducibility
  rm -rf "${base_root}" "${patch_root}" "${cand_dir}"
  mkdir -p "${cand_dir}"

  # 1) baseline
  export GRC_BFCL_TEST_CATEGORY="${subset}"
  bash scripts/run_bfcl_v4_baseline.sh "${MODEL_ALIAS}" "${base_root}"

  # 2) mine
  grc mine --trace-dir "${base_root}/traces" --out "${failures_out}"

  # 3) compile
  grc compile \
    --failures "${failures_out}" \
    --out "${rule_path}" \
    --patch-id "${patch_id}" \
    --candidate-dir "${cand_dir}"

  # 4) patch run
  bash scripts/run_bfcl_v4_patch.sh \
    "${MODEL_ALIAS}" \
    "${patch_root}" \
    8012 \
    "${subset}" \
    configs/runtime.yaml \
    "${cand_dir}" \
    "${patch_root}/traces" \
    "${cand_dir}" \
    "${base_root}/artifacts/metrics.json"

  # 5) select
  grc select \
    --baseline-metrics "${base_root}/artifacts/metrics.json" \
    --candidate-metrics "${cand_dir}/metrics.json" \
    --candidate-dir "${cand_dir}" \
    --rule-path "${rule_path}" \
    --accepted-dir rules/accepted \
    --rejected-dir rules/rejected \
    --active-dir rules/active \
    --out "${cand_dir}/accept.json"

  echo "done: ${subset}"
}

for s in "${SUBSETS[@]}"; do
  run_one_subset "$s"
done

unset GRC_BFCL_TEST_CATEGORY

echo
echo "All subsets finished."
echo "Check:"
echo "  - outputs/bfcl_v4/baseline/<subset>/artifacts/metrics.json"
echo "  - rules/candidates/patch_<subset>_001/accept.json"
echo "  - rules/accepted/ and rules/rejected/"
