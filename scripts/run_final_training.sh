#!/usr/bin/env bash
set -euo pipefail

DATA_PATH="${1:-data/processed/benchmark_team_routed_v6_global_family.csv}"
ESM_PATH="${2:-artifacts/final/esm150_embeddings.pt}"

python -m bioos_benchmark.inner_family_split \
  --input "$DATA_PATH" \
  --output data/processed/stage21_inner_family_holdout.csv

python -m bioos_benchmark.esm_parent_clusters \
  --input "$DATA_PATH" --embeddings "$ESM_PATH" \
  --output artifacts/final/outer_parent_clusters.joblib \
  --split-column global_family_v2_split --clusters-per-group 8 --seed 20260812

python -m bioos_benchmark.positional_neural_ranker \
  --input "$DATA_PATH" --artifact-dir artifacts/final/absolute_parent \
  --seed 20260812 --epochs 30 --batch-size 2048 --learning-rate 0.0003 \
  --rank-weight 0.04 --split-column global_family_v2_split \
  --task-route alphaseq_rank --deduplicate-biological \
  --parent-clusters artifacts/final/outer_parent_clusters.joblib

python -m bioos_benchmark.positional_neural_ranker \
  --input "$DATA_PATH" --artifact-dir artifacts/final/consensus_parent_delta \
  --seed 20260822 --epochs 30 --batch-size 2048 --learning-rate 0.0003 \
  --rank-weight 0.04 --split-column global_family_v2_split \
  --task-route alphaseq_rank --deduplicate-biological \
  --parent-clusters artifacts/final/outer_parent_clusters.joblib --parent-reference-delta

echo "Core Stage 21 parent models trained. Build the documented Stage 17 stable ensemble,"
echo "then run scripts/build_stage21_preregistered_outer_ensemble.py for the fixed rank blend."
