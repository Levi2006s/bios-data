from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import SGDRegressor

from .data import stable_bucket
from .features import AntibodyFeaturizer
from .metrics import regression_metrics


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def dataset_group(source_file: str) -> str:
    """Keep every file from the same numbered literature dataset together."""
    parts = source_file.replace("\\", "/").split("/")
    return "/".join(parts[:2]) if len(parts) >= 2 else source_file


def split_rows(rows: list[dict[str, str]], test_percent: int) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    groups = sorted({dataset_group(row["source_file"]) for row in rows})
    test_groups = {group for group in groups if stable_bucket(group) < test_percent}
    if not test_groups and groups:
        test_groups.add(groups[-1])
    if test_groups == set(groups) and len(groups) > 1:
        test_groups.remove(groups[0])
    train = [row for row in rows if dataset_group(row["source_file"]) not in test_groups]
    test = [row for row in rows if dataset_group(row["source_file"]) in test_groups]
    return train, test


def train_model(input_path: Path, artifact_dir: Path, seed: int, test_percent: int) -> dict[str, object]:
    rows = load_rows(input_path)
    train_rows, test_rows = split_rows(rows, test_percent)
    if not train_rows or not test_rows:
        raise ValueError("Need at least two source files to create a source-held-out split.")
    featurizer = AntibodyFeaturizer()
    x_train = featurizer.transform(train_rows)
    x_test = featurizer.transform(test_rows)
    y_train = np.asarray([float(row["score"]) for row in train_rows], dtype=np.float64)
    y_test = np.asarray([float(row["score"]) for row in test_rows], dtype=np.float64)
    model = SGDRegressor(
        loss="huber",
        penalty="elasticnet",
        alpha=1e-5,
        l1_ratio=0.05,
        max_iter=1000,
        tol=1e-4,
        random_state=seed,
        average=True,
    )
    model.fit(x_train, y_train)
    prediction = np.clip(model.predict(x_test), 0.0, 1.0)
    overall = regression_metrics(y_test, prediction)
    by_source: dict[str, dict[str, float]] = {}
    indices: defaultdict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(test_rows):
        indices[row["source_file"]].append(index)
    for source, positions in indices.items():
        idx = np.asarray(positions)
        by_source[source] = regression_metrics(y_test[idx], prediction[idx])
    valid_spearman = [x["spearman"] for x in by_source.values() if np.isfinite(x["spearman"])]
    metrics: dict[str, object] = {
        "split": "literature-dataset-group-held-out",
        "seed": seed,
        "train_records": len(train_rows),
        "test_records": len(test_rows),
        "train_sources": sorted({x["source_file"] for x in train_rows}),
        "test_sources": sorted({x["source_file"] for x in test_rows}),
        "train_dataset_groups": sorted({dataset_group(x["source_file"]) for x in train_rows}),
        "test_dataset_groups": sorted({dataset_group(x["source_file"]) for x in test_rows}),
        "overall": overall,
        "macro_source_spearman": float(np.mean(valid_spearman)) if valid_spearman else None,
        "by_source": by_source,
    }
    artifact_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "featurizer": featurizer, "metadata": metrics}, artifact_dir / "model.joblib")
    (artifact_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    with (artifact_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["record_id", "source_file", "truth", "prediction"])
        for row, truth, pred in zip(test_rows, y_test, prediction):
            writer.writerow([row["record_id"], row["source_file"], truth, pred])
    return metrics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train a leakage-aware sequence baseline.")
    parser.add_argument("--input", type=Path, default=Path("data/processed/benchmark.csv"))
    parser.add_argument("--artifact-dir", type=Path, default=Path("artifacts/baseline"))
    parser.add_argument("--seed", type=int, default=20260722)
    parser.add_argument("--test-percent", type=int, default=20)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    print(json.dumps(train_model(args.input, args.artifact_dir, args.seed, args.test_percent), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
