#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="$PROJECT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

DATA_PATH="${1:-data/processed/benchmark_team_routed_v6_global_family.csv}"
PREDICTIONS_PATH="${2:-artifacts/final/preregistered_outer_parent_delta_ensemble.csv}"
OUTPUT_PATH="${3:-deliverables/antibody_sequences.csv.gz}"

python scripts/export_submission_sequences.py \
  --data "$DATA_PATH" \
  --predictions "$PREDICTIONS_PATH" \
  --output "$OUTPUT_PATH"
