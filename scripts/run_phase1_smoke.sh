#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "${REPO_ROOT}/configs/bfcl_v4_phase1.env"

CONFIG_PATH="${1:-${REPO_ROOT}/configs/runtime.yaml}"
TRACE_DIR="${2:-${REPO_ROOT}/outputs/smoke/traces}"
ARTIFACT_DIR="${3:-${REPO_ROOT}/outputs/smoke/artifacts}"
BFCL_ROOT="${4:-${REPO_ROOT}/outputs/smoke/bfcl_fixture}"
PORT="${5:-8013}"

mkdir -p "${TRACE_DIR}" "${ARTIFACT_DIR}" "${BFCL_ROOT}"

PROXY_PID=""
cleanup() {
  if [[ -n "${PROXY_PID}" ]]; then
    kill "${PROXY_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" python -m grc.cli serve \
  --config "${CONFIG_PATH}" \
  --rules-dir "${REPO_ROOT}/rules/baseline_empty" \
  --trace-dir "${TRACE_DIR}" \
  --port "${PORT}" \
  >/tmp/grc_phase1_smoke_proxy.log 2>&1 &
PROXY_PID=$!

for _ in $(seq 1 40); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
    break
  fi
  sleep 1
done

curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null

SMOKE_REQUEST="$(mktemp)"
cat >"${SMOKE_REQUEST}" <<'EOF'
{
  "model": "smoke-model",
  "messages": [
    {"role": "user", "content": "Say hello"}
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "echo",
        "description": "Echo text",
        "parameters": {
          "type": "object",
          "properties": {
            "text": {"type": "string"}
          },
          "required": ["text"]
        }
      }
    }
  ]
}
EOF

SMOKE_RESPONSE="$(mktemp)"
HTTP_CODE="$(
  curl -sS -o "${SMOKE_RESPONSE}" -w '%{http_code}' \
    -H 'Content-Type: application/json' \
    -X POST "http://127.0.0.1:${PORT}/v1/chat/completions" \
    --data @"${SMOKE_REQUEST}"
)"

if [[ "${HTTP_CODE}" -ge 400 ]]; then
  echo "proxy upstream smoke request failed with HTTP ${HTTP_CODE}" >&2
  cat "${SMOKE_RESPONSE}" >&2
  exit 1
fi

LATEST_TRACE="$(find "${TRACE_DIR}" -maxdepth 1 -type f -name '*.json' | sort | tail -n 1)"
if [[ -z "${LATEST_TRACE}" ]]; then
  echo "smoke did not produce any trace file" >&2
  exit 1
fi

python - "${LATEST_TRACE}" <<'PY'
import json
import sys
from pathlib import Path

trace_path = Path(sys.argv[1])
payload = json.loads(trace_path.read_text(encoding="utf-8"))
required = ["request", "raw_response", "final_response", "validation", "latency_ms"]
missing = [key for key in required if key not in payload]
if missing:
    raise SystemExit(f"trace missing required keys: {missing}")
print(f"validated trace schema: {trace_path}")
PY

FIXTURE_METRICS="${BFCL_ROOT}/fixture_eval_metrics.json"
cat >"${FIXTURE_METRICS}" <<'EOF'
{
  "acc": 0.5,
  "cost": 0.1,
  "latency": 42.0,
  "subsets": {
    "smoke_subset": 0.5
  }
}
EOF

python "${REPO_ROOT}/scripts/aggregate_bfcl_metrics.py" \
  --bfcl-root "${BFCL_ROOT}" \
  --trace-dir "${TRACE_DIR}" \
  --out "${ARTIFACT_DIR}/metrics.json" \
  --repairs-out "${ARTIFACT_DIR}/repairs.jsonl" \
  --failure-summary-out "${ARTIFACT_DIR}/failure_summary.json" \
  --label "smoke" \
  --protocol-id "${GRC_PROTOCOL_ID}" \
  --model "${GRC_UPSTREAM_MODEL}" \
  --test-category "smoke"

python - "${ARTIFACT_DIR}/metrics.json" <<'PY'
import json
import sys
from pathlib import Path

metrics = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not metrics.get("metric_sources"):
    raise SystemExit("aggregate_bfcl_metrics.py did not discover any metric source")
print(json.dumps(metrics, ensure_ascii=False, indent=2))
PY
