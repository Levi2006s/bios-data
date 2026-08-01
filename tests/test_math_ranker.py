from __future__ import annotations

import csv
from pathlib import Path

import numpy as np

from bioos_benchmark.ranking.math_ranker import (
    BradleyTerryRanker,
    FeaturePairwiseRanker,
    predict_math_ranker,
    train_math_ranker,
)
from bioos_benchmark.ranking.preferences import (
    PreferencePair,
    build_preference_pairs,
    write_pairs,
)


def records() -> list[dict[str, str]]:
    return [
        {
            "record_id": "a",
            "heavy": "ACDE",
            "light": "",
            "antigen_seq": "ACDEFG",
            "source_file": "train.csv",
            "source_group": "train",
            "antigen_id": "x",
            "score": "0.1",
            "split": "train",
        },
        {
            "record_id": "b",
            "heavy": "ACDEFGHIK",
            "light": "",
            "antigen_seq": "ACDEFG",
            "source_file": "train.csv",
            "source_group": "train",
            "antigen_id": "x",
            "score": "0.5",
            "split": "train",
        },
        {
            "record_id": "c",
            "heavy": "ACDEFGHIKLMNPQRSTVWY",
            "light": "",
            "antigen_seq": "ACDEFG",
            "source_file": "train.csv",
            "source_group": "train",
            "antigen_id": "x",
            "score": "0.9",
            "split": "train",
        },
        {
            "record_id": "v1",
            "heavy": "ACDEF",
            "light": "",
            "antigen_seq": "ACDEFG",
            "source_file": "validation.csv",
            "source_group": "validation",
            "antigen_id": "x",
            "score": "0.2",
            "split": "validation",
        },
        {
            "record_id": "v2",
            "heavy": "ACDEFGHIKLMNPQR",
            "light": "",
            "antigen_seq": "ACDEFG",
            "source_file": "validation.csv",
            "source_group": "validation",
            "antigen_id": "x",
            "score": "0.8",
            "split": "validation",
        },
    ]


def test_bradley_terry_recovers_pair_order() -> None:
    pairs = [
        PreferencePair("b", "a", 1, 1.0, "g", "ordered_label"),
        PreferencePair("c", "b", 1, 1.0, "g", "ordered_label"),
        PreferencePair("c", "a", 1, 1.0, "g", "ordered_label"),
    ]
    ranker = BradleyTerryRanker(seed=3).fit(pairs, ["a", "b", "c"])
    scores = ranker.predict_score(["a", "b", "c"])
    assert scores[0] < scores[1] < scores[2]


def test_feature_pairwise_ranker_scores_and_roundtrips(tmp_path: Path) -> None:
    rows = records()
    train_rows = [row for row in rows if row["split"] == "train"]
    pairs = build_preference_pairs(train_rows)
    ranker = FeaturePairwiseRanker(n_features=256, seed=3).fit(train_rows, pairs)
    before = ranker.predict_score(rows)
    assert np.isfinite(before).all()
    assert ranker.pair_accuracy(train_rows, pairs) >= 0.5

    model_dir = tmp_path / "model"
    ranker.save(model_dir)
    loaded = FeaturePairwiseRanker.load(model_dir)
    after = loaded.predict_score(rows)
    np.testing.assert_allclose(before, after)


def test_train_and_predict_interfaces(tmp_path: Path) -> None:
    rows = records()
    input_path = tmp_path / "records.csv"
    pairs_path = tmp_path / "pairs.csv"
    artifact_dir = tmp_path / "artifact"
    output_path = tmp_path / "predictions.csv"

    with input_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    pairs = build_preference_pairs([row for row in rows if row["split"] == "train"])
    write_pairs(pairs_path, pairs)

    metrics = train_math_ranker(
        input_path,
        pairs_path,
        artifact_dir,
        n_features=256,
        seed=3,
        max_iter=500,
    )
    assert metrics["train_records"] == 3
    assert (artifact_dir / "model.joblib").exists()
    assert (artifact_dir / "predictions_validation.csv").exists()

    count = predict_math_ranker(
        artifact_dir,
        input_path,
        output_path,
        split="validation",
    )
    assert count == 2
    with output_path.open("r", encoding="utf-8", newline="") as handle:
        prediction_rows = list(csv.DictReader(handle))
    assert list(prediction_rows[0]) == [
        "record_id",
        "split",
        "source_group",
        "target_id",
        "y_true",
        "score",
        "model_id",
    ]
    assert len(prediction_rows) == 2
