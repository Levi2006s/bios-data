"""Quality-weighted global model with assay-aware regression experts."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import SGDRegressor

from .features import AntibodyFeaturizer
from .metrics import regression_metrics
from .train import dataset_group, load_rows, split_rows


def build_regressor(seed: int) -> SGDRegressor:
    return SGDRegressor(
        loss="huber", penalty="elasticnet", alpha=1e-5, l1_ratio=0.05,
        max_iter=1000, tol=1e-4, random_state=seed, average=True,
    )


def quality_weights(rows: list[dict[str, str]]) -> np.ndarray:
    values = []
    for row in rows:
        try:
            value = float(row.get("label_quality", "1") or 1)
        except ValueError:
            value = 1.0
        values.append(min(1.0, max(0.05, value)))
    return np.asarray(values, dtype=np.float64)


def safe_metric_key(row: dict[str, str], field: str) -> str:
    return str(row.get(field, "") or "unknown").strip() or "unknown"


def macro_metrics(
    rows: list[dict[str, str]], truth: np.ndarray, prediction: np.ndarray,
) -> tuple[dict[str, dict[str, float]], float | None, float | None, int]:
    indices: defaultdict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        indices[row["source_file"]].append(index)
    by_source = {}
    for source, positions in indices.items():
        idx = np.asarray(positions)
        by_source[source] = regression_metrics(truth[idx], prediction[idx])
    finite = [item["spearman"] for item in by_source.values() if math.isfinite(item["spearman"])]
    stable = [item["spearman"] for item in by_source.values() if item["n"] >= 20 and math.isfinite(item["spearman"])]
    return (
        by_source,
        float(np.mean(finite)) if finite else None,
        float(np.mean(stable)) if stable else None,
        len(stable),
    )


def train_experiment_aware(
    input_path: Path,
    artifact_dir: Path,
    *,
    seed: int = 42,
    split_column: str = "split",
    train_split: str = "train",
    evaluation_split: str = "validation",
    include_tiers: set[str] | None = None,
    max_rows_per_source: int = 50_000,
    expert_field: str = "metric",
    expert_min_records: int = 200,
    expert_blend: float = 0.5,
) -> dict[str, object]:
    if not 0 <= expert_blend <= 1:
        raise ValueError("expert_blend must be between 0 and 1")
    rows = load_rows(input_path, max_rows_per_source, seed, include_tiers)
    train_rows, evaluation_rows = split_rows(
        rows, 20, split_column, train_split, evaluation_split
    )
    if not train_rows or not evaluation_rows:
        raise ValueError("both train and evaluation rows are required")
    featurizer = AntibodyFeaturizer()
    x_train = featurizer.transform(train_rows)
    x_evaluation = featurizer.transform(evaluation_rows)
    y_train = np.asarray([float(row["score"]) for row in train_rows])
    y_evaluation = np.asarray([float(row["score"]) for row in evaluation_rows])
    weights = quality_weights(train_rows)

    global_model = build_regressor(seed)
    global_model.fit(x_train, y_train, sample_weight=weights)
    global_prediction = np.clip(global_model.predict(x_evaluation), 0.0, 1.0)
    expert_prediction = global_prediction.copy()
    blended_prediction = global_prediction.copy()

    train_groups: defaultdict[str, list[int]] = defaultdict(list)
    evaluation_groups: defaultdict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(train_rows):
        train_groups[safe_metric_key(row, expert_field)].append(index)
    for index, row in enumerate(evaluation_rows):
        evaluation_groups[safe_metric_key(row, expert_field)].append(index)

    experts: dict[str, SGDRegressor] = {}
    expert_metadata = {}
    for offset, key in enumerate(sorted(train_groups)):
        train_idx = np.asarray(train_groups[key])
        eval_idx = np.asarray(evaluation_groups.get(key, []))
        if len(train_idx) < expert_min_records:
            expert_metadata[key] = {"train_records": len(train_idx), "evaluation_records": len(eval_idx), "status": "fallback_global"}
            continue
        model = build_regressor(seed + offset + 1)
        model.fit(x_train[train_idx], y_train[train_idx], sample_weight=weights[train_idx])
        experts[key] = model
        if len(eval_idx):
            metric_prediction = np.clip(model.predict(x_evaluation[eval_idx]), 0.0, 1.0)
            expert_prediction[eval_idx] = metric_prediction
            blended_prediction[eval_idx] = (
                (1.0 - expert_blend) * global_prediction[eval_idx]
                + expert_blend * metric_prediction
            )
        expert_metadata[key] = {"train_records": len(train_idx), "evaluation_records": len(eval_idx), "status": "trained"}

    overall = regression_metrics(y_evaluation, blended_prediction)
    global_only = regression_metrics(y_evaluation, global_prediction)
    by_source, macro, stable_macro, stable_count = macro_metrics(
        evaluation_rows, y_evaluation, blended_prediction
    )
    metrics: dict[str, object] = {
        "model": "quality_weighted_global_plus_assay_experts",
        "seed": seed, "split_column": split_column,
        "train_split": train_split, "evaluation_split": evaluation_split,
        "include_tiers": sorted(include_tiers) if include_tiers else None,
        "max_rows_per_source": max_rows_per_source,
        "expert_field": expert_field, "expert_min_records": expert_min_records,
        "expert_blend": expert_blend, "train_records": len(train_rows),
        "evaluation_records": len(evaluation_rows), "trained_experts": len(experts),
        "experts": expert_metadata, "global_only": global_only, "overall": overall,
        "macro_source_spearman": macro,
        "macro_source_spearman_min_n_20": stable_macro,
        "macro_source_count_min_n_20": stable_count,
        "by_source": by_source,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"global_model": global_model, "experts": experts, "featurizer": featurizer,
         "expert_field": expert_field, "expert_blend": expert_blend, "metadata": metrics},
        artifact_dir / "model.joblib",
    )
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with (artifact_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["record_id", "source_file", "metric", "truth", "global_prediction", "expert_prediction", "prediction"])
        for row, truth, global_score, expert_score, score in zip(
            evaluation_rows, y_evaluation, global_prediction, expert_prediction, blended_prediction
        ):
            writer.writerow([row["record_id"], row["source_file"], row.get("metric", ""), truth, global_score, expert_score, score])
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--split-column", default="split")
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--evaluation-split", default="validation")
    parser.add_argument("--include-tiers", nargs="*")
    parser.add_argument("--max-rows-per-source", type=int, default=50_000)
    parser.add_argument("--expert-field", default="metric")
    parser.add_argument("--expert-min-records", type=int, default=200)
    parser.add_argument("--expert-blend", type=float, default=0.5)
    args = parser.parse_args()
    metrics = train_experiment_aware(
        args.input, args.artifact_dir, seed=args.seed,
        split_column=args.split_column, train_split=args.train_split,
        evaluation_split=args.evaluation_split,
        include_tiers=set(args.include_tiers) if args.include_tiers else None,
        max_rows_per_source=args.max_rows_per_source, expert_field=args.expert_field,
        expert_min_records=args.expert_min_records, expert_blend=args.expert_blend,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
