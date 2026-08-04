#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: bash scripts/run_data_pipeline.sh DATA_ROOT [MAX_ROWS_PER_FILE]" >&2
  exit 2
fi

DATA_ROOT="$1"
MAX_ROWS="${2:-5000}"
export PYTHONPATH=src

python -m bioos_benchmark.audit \
  --data-root "$DATA_ROOT" \
  --output data/processed/audit.csv \
  --hash-inputs

python -m bioos_benchmark.prepare \
  --data-root "$DATA_ROOT" \
  --output data/processed/benchmark.csv \
  --max-rows-per-file "$MAX_ROWS" \
  --direction-overrides configs/direction_overrides.csv \
  --label-registry configs/label_registry.csv

python -m bioos_benchmark.curation \
  --data-root "$DATA_ROOT" \
  --registry configs/label_registry.csv \
  --audit data/processed/audit.csv \
  --output-dir data/processed/curation

python -m bioos_benchmark.apply_splits \
  --input data/processed/benchmark.csv \
  --manifest data/processed/curation/split_group_manifest.csv \
  --output data/processed/benchmark_with_group_splits.csv

python -m bioos_benchmark.identity_split \
  --input data/processed/benchmark_with_group_splits.csv \
  --output data/processed/benchmark_with_split.csv \
  --column split

python -m bioos_benchmark.validate \
  --input data/processed/benchmark_with_split.csv \
  --report data/processed/validation_report.json

echo "Data pipeline completed: data/processed"
