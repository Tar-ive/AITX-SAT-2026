#!/usr/bin/env bash
# One RSI evaluation cycle: verifiers rollouts against Nemotron with the
# CURRENT episodic-memory lessons -> scored results -> dashboard CSV row.
#
# Usage:
#   scripts/run_rsi_cycle.sh v1.5 "nightly lessons 07-19" [memory/lessons.md]
#
# Prereqs (once):  uv tool install verifiers  (or: pip install verifiers)
#                  vf-install ./environments/gpu_deal_judge
# Env: NVIDIA_INFERENCE_API_KEY (or NVIDIA_API_KEY in repo .env)
set -euo pipefail

VERSION="${1:?version tag, e.g. v1.5}"
POLICY_CHANGE="${2:?short description of what changed}"
MEMORY_FILE="${3:-}"

REPO="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO"
set -a; [ -f .env ] && . ./.env; set +a
export OPENAI_API_KEY="${NVIDIA_INFERENCE_API_KEY:-$NVIDIA_API_KEY}"

MODEL="nvidia/nemotron-3-super-120b-a12b"
ARGS=()
[ -n "$MEMORY_FILE" ] && ARGS+=(--env-args "{\"memory_file\": \"$MEMORY_FILE\"}")

echo "[rsi] rollouts: model=$MODEL version=$VERSION memory=${MEMORY_FILE:-none}"
vf-eval gpu-deal-judge \
  -m "$MODEL" \
  -b "https://integrate.api.nvidia.com/v1" \
  -n 15 -r 3 -s \
  "${ARGS[@]}"

RESULTS=$(ls -t outputs/evals/gpu-deal-judge*/*/results.jsonl 2>/dev/null | head -1)
[ -n "$RESULTS" ] || { echo "[rsi] no results file found under outputs/"; exit 1; }
echo "[rsi] results: $RESULTS"

python3 scripts/verifiers_to_rsi_csv.py "$RESULTS" \
  --output data/rsi_runs.csv \
  --run-id "${VERSION}-$(date -u +%Y%m%dT%H%M)" \
  --version "$VERSION" \
  --policy-change "$POLICY_CHANGE" \
  --teacher-model Nemotron \
  --accepted false \
  --current false

echo "[rsi] appended to data/rsi_runs.csv — dashboard 'Refresh history' will show it."
echo "[rsi] promote by re-running verifiers_to_rsi_csv.py with --accepted true after review."
