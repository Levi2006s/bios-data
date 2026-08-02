from __future__ import annotations

import csv
from pathlib import Path

import pytest

from bioos_benchmark.ranking.ensemble import (
    ensemble_predictions,
    percentile_rank_by_group,
    scores_to_submission,
)
from bioos_benchmark.ranking.evaluation import evaluate_predictions


def truth_rows() -> list[dict[str, str]]:
    rows = []
    scores = [0.1, 0.3, 0.8, 0.2, 0.6, 0.9]
    for index, score in enumerate(scores):
        rows.append(
            {
                "record_id": f"r{index}",
                "heavy": "ACDEFGHIK" + "A" * index,
                "light": "" if index % 2 else "ACDE",
                "source_group": "s1" if index < 3 else "s2",
                "antigen_id": "t1" if index < 3 else "t2",
                "score": str(score),
                "split": "validation",
                "split_group": "s1" if index < 3 else "s2",
                "is_censored": "1" if index == 0 else "0",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def prediction_rows(rows: list[dict[str, str]], reverse: bool = False) -> list[dict[str, str]]:
    result = []
    for row in rows:
        score = float(row["score"])
        result.append(
            {
                "record_id": row["record_id"],
                "split": row["split"],
                "source_group": row["source_group"],
                "target_id": row["antigen_id"],
                "y_true": row["score"],
                "score": str(-score if reverse else score),
                "model_id": "reverse" if reverse else "perfect",
            }
        )
    return result


def test_evaluate_perfect_predictions_and_bootstrap(tmp_path: Path) -> None:
    truth = tmp_path / "truth.csv"
    predictions = tmp_path / "predictions.csv"
    rows = truth_rows()
    write_csv(truth, rows)
    write_csv(predictions, list(reversed(prediction_rows(rows))))

    report = evaluate_predictions(truth, predictions, bootstrap_rounds=50, seed=4)
    assert report["global"]["spearman"] == pytest.approx(1.0)
    assert report["macro_source_spearman"] == pytest.approx(1.0)
    assert report["bootstrap_spearman_95ci"]["low"] == pytest.approx(1.0)
    assert report["bootstrap_top10_enrichment_95ci"]["low"] is not None
    assert report["global"]["top1_enrichment"] >= 1.0
    assert report["global"]["top5_enrichment"] >= 1.0
    assert report["model_selection_composite"] is None


def test_evaluation_rejects_id_mismatch(tmp_path: Path) -> None:
    truth = tmp_path / "truth.csv"
    predictions = tmp_path / "predictions.csv"
    rows = truth_rows()
    write_csv(truth, rows)
    write_csv(predictions, prediction_rows(rows)[:-1])
    with pytest.raises(ValueError, match="record_id mismatch"):
        evaluate_predictions(truth, predictions, bootstrap_rounds=0)


def test_evaluation_can_filter_full_truth_by_split(tmp_path: Path) -> None:
    truth = tmp_path / "truth.csv"
    predictions = tmp_path / "predictions.csv"
    rows = truth_rows()
    rows[0]["split"] = "train"
    write_csv(truth, rows)
    write_csv(predictions, prediction_rows(rows[1:]))
    report = evaluate_predictions(
        truth,
        predictions,
        bootstrap_rounds=0,
        split="validation",
    )
    assert report["records_total"] == 5
    assert report["split_filter"] == "validation"


def test_percentile_rank_handles_groups_and_ties() -> None:
    values = percentile_rank_by_group([1.0, 2.0, 2.0, 10.0], ["a", "a", "a", "b"])
    assert values == [0.0, 0.75, 0.75, 0.5]


def test_ensemble_aligns_ids_and_writes_summary(tmp_path: Path) -> None:
    rows = truth_rows()
    truth = tmp_path / "truth.csv"
    first = tmp_path / "first.csv"
    second = tmp_path / "second.csv"
    output = tmp_path / "ensemble.csv"
    write_csv(truth, rows)
    write_csv(first, prediction_rows(rows))
    write_csv(second, list(reversed(prediction_rows(rows, reverse=True))))

    report = ensemble_predictions([first, second], output, weights=[0.8, 0.2])
    assert report["records"] == 6
    assert report["weights"] == pytest.approx([0.8, 0.2])
    assert output.exists()
    assert output.with_suffix(".summary.json").exists()
    evaluation = evaluate_predictions(truth, output, bootstrap_rounds=0)
    assert evaluation["macro_source_spearman"] == pytest.approx(1.0)
    assert evaluation["global"]["spearman"] > 0.9


def test_submission_has_continuous_rank_and_blank_vhh_light(tmp_path: Path) -> None:
    rows = truth_rows()
    records = tmp_path / "records.csv"
    predictions = tmp_path / "predictions.csv"
    submission = tmp_path / "submission.csv"
    write_csv(records, rows)
    write_csv(predictions, prediction_rows(rows))

    report = scores_to_submission(records, predictions, submission)
    assert report["rank_min"] == 1
    assert report["rank_max"] == 6
    with submission.open("r", encoding="utf-8", newline="") as handle:
        submitted = list(csv.DictReader(handle))
    assert [int(row["Rank"]) for row in submitted] == list(range(1, 7))
    assert submitted[0]["VH/VHH"] == rows[5]["heavy"]
    assert submitted[0]["VL"] == ""
