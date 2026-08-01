#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <benchmark_with_split.csv> [work_dir] [seed]"
  exit 2
fi

INPUT="$1"
WORK_DIR="${2:-artifacts/math}"
SEED="${3:-42}"
MAX_PAIRS_PER_GROUP="${MAX_PAIRS_PER_GROUP:-100000}"
MAX_PAIRS_TOTAL="${MAX_PAIRS_TOTAL:-1000000}"
export PYTHONPATH="$(cd "$(dirname "$0")/../src" && pwd)"
LOCAL_PYTHON="$(cd "$(dirname "$0")/.." && pwd)/.venv/bin/python"
if [[ -z "${PYTHON:-}" && -x "$LOCAL_PYTHON" ]]; then
  PYTHON="$LOCAL_PYTHON"
else
  PYTHON="${PYTHON:-python}"
fi

mkdir -p "$WORK_DIR"

"$PYTHON" -m bioos_benchmark.ranking.preferences \
  --input "$INPUT" \
  --output "$WORK_DIR/pairs_train.csv" \
  --split train \
  --max-pairs-per-group "$MAX_PAIRS_PER_GROUP" \
  --max-pairs-total "$MAX_PAIRS_TOTAL" \
  --seed "$SEED"

"$PYTHON" -m bioos_benchmark.ranking.math_ranker train \
  --input "$INPUT" \
  --pairs "$WORK_DIR/pairs_train.csv" \
  --artifact-dir "$WORK_DIR/model" \
  --seed "$SEED"

"$PYTHON" -m bioos_benchmark.ranking.math_ranker predict \
  --model-dir "$WORK_DIR/model" \
  --input "$INPUT" \
  --split validation \
  --output "$WORK_DIR/predictions_validation.csv"

"$PYTHON" -m bioos_benchmark.ranking.evaluation \
  --truth "$INPUT" \
  --predictions "$WORK_DIR/predictions_validation.csv" \
  --split validation \
  --output "$WORK_DIR/evaluation_validation.json" \
  --seed "$SEED"

"$PYTHON" -m bioos_benchmark.ranking.math_ranker predict \
  --model-dir "$WORK_DIR/model" \
  --input "$INPUT" \
  --split test \
  --output "$WORK_DIR/predictions_test.csv"

"$PYTHON" -m bioos_benchmark.ranking.ensemble submit \
  --input "$INPUT" \
  --predictions "$WORK_DIR/predictions_test.csv" \
  --split test \
  --output "$WORK_DIR/submission.csv"

echo "Math ranking pipeline completed."
echo "Validation report: $WORK_DIR/evaluation_validation.json"
echo "Submission: $WORK_DIR/submission.csv"
