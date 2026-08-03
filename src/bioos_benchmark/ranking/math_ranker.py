from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Mapping, Sequence

import joblib
import numpy as np
from scipy import sparse
from sklearn.linear_model import SGDClassifier

from ..features import AntibodyFeaturizer
from ..metrics import regression_metrics
from .preferences import PreferencePair, oriented_label


def _record_id(row: Mapping[str, object]) -> str:
    return str(row.get("record_id", "") or "").strip()


def _read_rows(path: Path, include_tiers: set[str] | None = None) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if include_tiers:
        rows = [row for row in rows if str(row.get("tier", "")).strip() in include_tiers]
    ids = [_record_id(row) for row in rows]
    if not rows or any(not item for item in ids):
        raise ValueError("Input must be a non-empty CSV with record_id.")
    if len(ids) != len(set(ids)):
        raise ValueError("Input contains duplicate record_id values.")
    return rows


def _read_pairs(path: Path) -> list[PreferencePair]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    pairs: list[PreferencePair] = []
    for row in rows:
        pairs.append(
            PreferencePair(
                left_record_id=str(row["left_record_id"]),
                right_record_id=str(row["right_record_id"]),
                preference=int(row["preference"]),
                pair_weight=float(row["pair_weight"]),
                comparison_group=str(row["comparison_group"]),
                reason=str(row.get("reason", "")),
            )
        )
    if not pairs:
        raise ValueError("Pair file is empty.")
    return pairs


def _build_classifier(seed: int, alpha: float, max_iter: int) -> SGDClassifier:
    return SGDClassifier(
        loss="log_loss",
        penalty="elasticnet",
        alpha=alpha,
        l1_ratio=0.05,
        max_iter=max_iter,
        tol=1e-5,
        random_state=seed,
        average=True,
        fit_intercept=False,
    )


class BradleyTerryRanker:
    """Transductive Bradley-Terry model used to audit a preference graph."""

    def __init__(self, *, seed: int = 42, alpha: float = 1e-4, max_iter: int = 2000):
        self.seed = seed
        self.alpha = alpha
        self.max_iter = max_iter
        self.record_ids_: list[str] = []
        self.scores_: dict[str, float] = {}
        self.model_: SGDClassifier | None = None

    def fit(
        self,
        pairs: Sequence[PreferencePair],
        record_ids: Sequence[str],
    ) -> "BradleyTerryRanker":
        self.record_ids_ = sorted(set(record_ids))
        index = {record_id: position for position, record_id in enumerate(self.record_ids_)}
        if len(index) < 2:
            raise ValueError("Bradley-Terry requires at least two records.")
        rows: list[int] = []
        columns: list[int] = []
        values: list[float] = []
        weights: list[float] = []
        used_pairs = 0
        for pair in pairs:
            if pair.left_record_id not in index or pair.right_record_id not in index:
                continue
            sign = float(pair.preference)
            row_index = used_pairs
            rows.extend([row_index, row_index])
            columns.extend([index[pair.left_record_id], index[pair.right_record_id]])
            values.extend([sign, -sign])
            weights.append(pair.pair_weight)
            used_pairs += 1
        if used_pairs == 0:
            raise ValueError("No preference pairs match the supplied record_ids.")
        difference = sparse.csr_matrix(
            (values, (rows, columns)),
            shape=(used_pairs, len(index)),
            dtype=np.float64,
        )
        training_x = sparse.vstack([difference, -difference], format="csr")
        training_y = np.concatenate(
            [np.ones(used_pairs, dtype=np.int8), np.zeros(used_pairs, dtype=np.int8)]
        )
        sample_weight = np.asarray(weights + weights, dtype=np.float64)
        model = _build_classifier(self.seed, self.alpha, self.max_iter)
        model.fit(training_x, training_y, sample_weight=sample_weight)
        raw_scores = np.asarray(model.coef_[0], dtype=np.float64)
        raw_scores -= raw_scores.mean()
        self.model_ = model
        self.scores_ = dict(zip(self.record_ids_, raw_scores.tolist()))
        return self

    def predict_score(self, record_ids: Sequence[str]) -> list[float]:
        missing = [record_id for record_id in record_ids if record_id not in self.scores_]
        if missing:
            raise KeyError(
                "Bradley-Terry is transductive and cannot score unseen IDs: "
                + ", ".join(missing[:5])
            )
        return [self.scores_[record_id] for record_id in record_ids]


class FeaturePairwiseRanker:
    """Inductive pairwise logistic ranker over antibody/antigen sequence features."""

    def __init__(
        self,
        *,
        n_features: int = 2**16,
        seed: int = 42,
        alpha: float = 1e-5,
        max_iter: int = 2000,
        model_id: str = "math_pairwise_v1",
    ):
        self.n_features = n_features
        self.seed = seed
        self.alpha = alpha
        self.max_iter = max_iter
        self.model_id = model_id
        self.featurizer = AntibodyFeaturizer(n_features=n_features)
        self.model: SGDClassifier | None = None

    def fit(
        self,
        records: Sequence[dict[str, str]],
        pairs: Sequence[PreferencePair],
    ) -> "FeaturePairwiseRanker":
        lookup = {_record_id(row): row for row in records}
        if len(lookup) != len(records):
            raise ValueError("Training records contain duplicate record_id values.")
        used_pairs = [
            pair
            for pair in pairs
            if pair.left_record_id in lookup and pair.right_record_id in lookup
        ]
        if not used_pairs:
            raise ValueError("No preference pairs match the training records.")
        unique_ids = sorted(
            {
                record_id
                for pair in used_pairs
                for record_id in (pair.left_record_id, pair.right_record_id)
            }
        )
        feature_rows = [lookup[record_id] for record_id in unique_ids]
        features = self.featurizer.transform(feature_rows)
        positions = {record_id: index for index, record_id in enumerate(unique_ids)}
        left_indices = np.asarray([positions[pair.left_record_id] for pair in used_pairs])
        right_indices = np.asarray([positions[pair.right_record_id] for pair in used_pairs])
        signs = np.asarray([pair.preference for pair in used_pairs], dtype=np.float64)
        difference = features[left_indices] - features[right_indices]
        difference = difference.multiply(signs[:, None]).tocsr()
        training_x = sparse.vstack([difference, -difference], format="csr")
        count = len(used_pairs)
        training_y = np.concatenate(
            [np.ones(count, dtype=np.int8), np.zeros(count, dtype=np.int8)]
        )
        weights = np.asarray([pair.pair_weight for pair in used_pairs], dtype=np.float64)
        sample_weight = np.concatenate([weights, weights])
        self.model = _build_classifier(self.seed, self.alpha, self.max_iter)
        self.model.fit(training_x, training_y, sample_weight=sample_weight)
        return self

    def predict_score(self, records: Sequence[dict[str, str]]) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("Ranker must be fitted or loaded before prediction.")
        features = self.featurizer.transform(list(records))
        return np.asarray(self.model.decision_function(features), dtype=np.float64)

    def pair_accuracy(
        self,
        records: Sequence[dict[str, str]],
        pairs: Sequence[PreferencePair],
    ) -> float:
        lookup = {_record_id(row): row for row in records}
        scores = dict(
            zip(
                lookup,
                self.predict_score([lookup[record_id] for record_id in lookup]).tolist(),
            )
        )
        correct_weight = 0.0
        total_weight = 0.0
        for pair in pairs:
            if pair.left_record_id not in scores or pair.right_record_id not in scores:
                continue
            difference = scores[pair.left_record_id] - scores[pair.right_record_id]
            if difference * pair.preference > 0:
                correct_weight += pair.pair_weight
            elif difference == 0:
                correct_weight += 0.5 * pair.pair_weight
            total_weight += pair.pair_weight
        return correct_weight / total_weight if total_weight else float("nan")

    def save(self, output_dir: Path) -> None:
        if self.model is None:
            raise RuntimeError("Cannot save an unfitted ranker.")
        output_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, output_dir / "model.joblib")
        metadata = {
            "model_id": self.model_id,
            "n_features": self.n_features,
            "seed": self.seed,
            "alpha": self.alpha,
            "max_iter": self.max_iter,
            "score_direction": "larger is better",
        }
        (output_dir / "config.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, model_dir: Path) -> "FeaturePairwiseRanker":
        model = joblib.load(model_dir / "model.joblib")
        if not isinstance(model, cls):
            raise TypeError("Saved artifact is not a FeaturePairwiseRanker.")
        return model


def _split_rows(rows: Sequence[dict[str, str]], split: str) -> list[dict[str, str]]:
    return [row for row in rows if str(row.get("split", "")).strip() == split]


def _prediction_metrics(rows: Sequence[dict[str, str]], scores: np.ndarray) -> dict[str, float] | None:
    labels: list[float] = []
    usable_scores: list[float] = []
    for row, score in zip(rows, scores):
        label = oriented_label(row)
        if label is not None and math.isfinite(score):
            labels.append(label)
            usable_scores.append(float(score))
    if len(labels) < 2:
        return None
    return regression_metrics(
        np.asarray(labels, dtype=np.float64),
        np.asarray(usable_scores, dtype=np.float64),
    )


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def write_predictions(
    path: Path,
    rows: Sequence[dict[str, str]],
    scores: Sequence[float],
    model_id: str,
) -> None:
    if len(rows) != len(scores):
        raise ValueError("Prediction count does not match input rows.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["record_id", "split", "source_group", "target_id", "y_true", "score", "model_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row, score in zip(rows, scores):
            number = float(score)
            if not math.isfinite(number):
                raise ValueError(f"Non-finite score for record {_record_id(row)}")
            label = oriented_label(row)
            writer.writerow(
                {
                    "record_id": _record_id(row),
                    "split": row.get("split", ""),
                    "source_group": row.get("source_group", ""),
                    "target_id": row.get("target_id", row.get("antigen_id", "")),
                    "y_true": "" if label is None else f"{label:.12g}",
                    "score": f"{number:.12g}",
                    "model_id": model_id,
                }
            )


def train_math_ranker(
    input_path: Path,
    pairs_path: Path,
    artifact_dir: Path,
    *,
    train_split: str = "train",
    validation_split: str = "validation",
    n_features: int = 2**16,
    seed: int = 42,
    alpha: float = 1e-5,
    max_iter: int = 2000,
    include_tiers: set[str] | None = None,
    split_column: str = "split",
) -> dict[str, object]:
    rows = _read_rows(input_path, include_tiers)
    if rows and split_column not in rows[0]:
        raise ValueError(f"Split column not found: {split_column}")
    pairs = _read_pairs(pairs_path)
    train_rows = [row for row in rows if str(row.get(split_column, "")).strip() == train_split]
    validation_rows = [row for row in rows if str(row.get(split_column, "")).strip() == validation_split]
    if not train_rows:
        raise ValueError(f"No rows found for train split: {train_split}")
    ranker = FeaturePairwiseRanker(
        n_features=n_features,
        seed=seed,
        alpha=alpha,
        max_iter=max_iter,
    )
    ranker.fit(train_rows, pairs)
    train_pair_accuracy = ranker.pair_accuracy(train_rows, pairs)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    ranker.save(artifact_dir)
    metrics: dict[str, object] = {
        "model_id": ranker.model_id,
        "train_records": len(train_rows),
        "train_pairs": len(pairs),
        "train_pair_accuracy": train_pair_accuracy,
        "validation_records": len(validation_rows),
        "seed": seed,
        "n_features": n_features,
        "alpha": alpha,
        "max_iter": max_iter,
        "include_tiers": sorted(include_tiers) if include_tiers else None,
        "split_column": split_column,
    }
    if validation_rows:
        validation_scores = ranker.predict_score(validation_rows)
        metrics["validation"] = _prediction_metrics(validation_rows, validation_scores)
        write_predictions(
            artifact_dir / "predictions_validation.csv",
            validation_rows,
            validation_scores,
            ranker.model_id,
        )
    metrics = _json_safe(metrics)
    (artifact_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    return metrics


def predict_math_ranker(
    model_dir: Path,
    input_path: Path,
    output_path: Path,
    *,
    split: str | None = None,
) -> int:
    rows = _read_rows(input_path)
    if split:
        rows = _split_rows(rows, split)
    ranker = FeaturePairwiseRanker.load(model_dir)
    scores = ranker.predict_score(rows)
    write_predictions(output_path, rows, scores, ranker.model_id)
    return len(rows)


def train_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Train the mathematical pairwise affinity ranker.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--validation-split", default="validation")
    parser.add_argument("--split-column", default="split")
    parser.add_argument("--n-features", type=int, default=2**16)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--alpha", type=float, default=1e-5)
    parser.add_argument("--max-iter", type=int, default=2000)
    parser.add_argument("--include-tiers", nargs="*")
    return parser


def predict_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Score records with the mathematical ranker.")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split")
    return parser


def main_train() -> None:
    args = train_parser().parse_args()
    metrics = train_math_ranker(
        args.input,
        args.pairs,
        args.artifact_dir,
        train_split=args.train_split,
        validation_split=args.validation_split,
        n_features=args.n_features,
        seed=args.seed,
        alpha=args.alpha,
        max_iter=args.max_iter,
        include_tiers=set(args.include_tiers) if args.include_tiers else None,
        split_column=args.split_column,
    )
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


def main_predict() -> None:
    args = predict_parser().parse_args()
    count = predict_math_ranker(
        args.model_dir,
        args.input,
        args.output,
        split=args.split,
    )
    print(json.dumps({"output": str(args.output), "records": count}, ensure_ascii=False, indent=2))


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in {"train", "predict"}:
        raise SystemExit(
            "Usage: python -m bioos_benchmark.ranking.math_ranker "
            "{train|predict} [arguments]"
        )
    command = sys.argv[1]
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    if command == "train":
        main_train()
    else:
        main_predict()


if __name__ == "__main__":
    main()
