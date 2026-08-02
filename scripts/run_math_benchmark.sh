#!/usr/bin/env bash
set -euo pipefail

INPUT_PATH="${1:-data/processed/curation/curated_sample_with_splits.csv}"
WORK_DIR="${2:-artifacts/math_benchmark}"
SPLIT_COLUMN="${3:-paper_split}"
EVALUATION_SPLIT="${4:-validation}"
LABEL_REGISTRY="${5:-configs/label_registry.csv}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$ROOT/src"
PYTHON="${PYTHON:-python}"
mkdir -p "$WORK_DIR"

"$PYTHON" -m bioos_benchmark.ranking.prepare \
  --input "$INPUT_PATH" --output "$WORK_DIR/dataset.csv" \
  --split-column "$SPLIT_COLUMN" --label-registry "$LABEL_REGISTRY"
"$PYTHON" -m bioos_benchmark.ranking.preferences \
  --input "$WORK_DIR/dataset.csv" --output "$WORK_DIR/pairs_train.csv" \
  --split train --max-pairs-per-group 20000 --max-pairs-total 200000 --seed 42

for seed in 42 43; do
  "$PYTHON" -m bioos_benchmark.ranking.math_ranker train \
    --input "$WORK_DIR/dataset.csv" --pairs "$WORK_DIR/pairs_train.csv" \
    --artifact-dir "$WORK_DIR/model_seed${seed}" --seed "$seed"
  "$PYTHON" -m bioos_benchmark.ranking.math_ranker predict \
    --model-dir "$WORK_DIR/model_seed${seed}" --input "$WORK_DIR/dataset.csv" \
    --split "$EVALUATION_SPLIT" --output "$WORK_DIR/predictions_${EVALUATION_SPLIT}_seed${seed}.csv"
  "$PYTHON" -m bioos_benchmark.ranking.evaluation \
    --truth "$WORK_DIR/dataset.csv" \
    --predictions "$WORK_DIR/predictions_${EVALUATION_SPLIT}_seed${seed}.csv" \
    --split "$EVALUATION_SPLIT" --bootstrap-rounds 1000 --seed "$seed" \
    --output "$WORK_DIR/evaluation_${EVALUATION_SPLIT}_seed${seed}.json"
done

"$PYTHON" -m bioos_benchmark.ranking.ensemble ensemble \
  --inputs "$WORK_DIR/predictions_${EVALUATION_SPLIT}_seed42.csv" "$WORK_DIR/predictions_${EVALUATION_SPLIT}_seed43.csv" \
  --weights 0.5 0.5 --group-field target_id --output "$WORK_DIR/ensemble_${EVALUATION_SPLIT}.csv"
"$PYTHON" -m bioos_benchmark.ranking.evaluation \
  --truth "$WORK_DIR/dataset.csv" --predictions "$WORK_DIR/ensemble_${EVALUATION_SPLIT}.csv" \
  --split "$EVALUATION_SPLIT" --bootstrap-rounds 1000 --seed 44 \
  --output "$WORK_DIR/evaluation_ensemble_${EVALUATION_SPLIT}.json"
"$PYTHON" -m bioos_benchmark.ranking.leakage \
  --truth "$WORK_DIR/dataset.csv" --predictions "$WORK_DIR/ensemble_${EVALUATION_SPLIT}.csv" \
  --evaluation-split "$EVALUATION_SPLIT" --output "$WORK_DIR/shortcut_audit_${EVALUATION_SPLIT}.json"

echo "Mathematical benchmark completed: $WORK_DIR"
