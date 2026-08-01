#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: bash scripts/run_demo.sh /path/to/第四届Bio-OS开源大赛数据" >&2
  exit 2
fi

export PYTHONPATH=src

python -m bioos_benchmark.prepare \
  --data-root "$1" \
  --output data/processed/benchmark.csv \
  --max-rows-per-file 5000

python -m bioos_benchmark.train \
  --input data/processed/benchmark.csv \
  --artifact-dir artifacts/baseline

python -m bioos_benchmark.design \
  --model artifacts/baseline/model.joblib \
  --target examples/target.json \
  --output artifacts/candidates.csv \
  --count 1000

echo "Demo complete. See artifacts/baseline and artifacts/candidates.csv"

