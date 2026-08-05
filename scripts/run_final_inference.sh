#!/usr/bin/env bash
set -euo pipefail

DATA_PATH="${1:-data/processed/benchmark_team_routed_v6_global_family.csv}"
PREDICTIONS_PATH="${2:-artifacts/final/preregistered_outer_parent_delta_ensemble.csv}"
OUTPUT_PATH="${3:-deliverables/antibody_sequences.csv.gz}"

python scripts/export_submission_sequences.py \
  --data "$DATA_PATH" \
  --predictions "$PREDICTIONS_PATH" \
  --output "$OUTPUT_PATH"
