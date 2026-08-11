"""Evaluate rank ensembles on the intersection of validation predictions."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from ..experiment_train import macro_metrics
from ..metrics import regression_metrics
from .ensemble import percentile_rank_by_group


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sweep_validation_ensemble(
    pointwise_rows: list[dict[str, str]],
    pairwise_rows: list[dict[str, str]],
    pairwise_weights: list[float],
) -> dict[str, object]:
    pair_lookup = {row["record_id"]: row for row in pairwise_rows}
    aligned = [(row, pair_lookup[row["record_id"]]) for row in pointwise_rows if row["record_id"] in pair_lookup]
    if not aligned:
        raise ValueError("prediction files have no record_id intersection")
    rows = [{"source_file": left.get("source_file", right.get("source_group", ""))} for left, right in aligned]
    groups = [right.get("target_id", "") or row["source_file"] for row, (_, right) in zip(rows, aligned)]
    truth = np.asarray([float(left.get("truth", left.get("y_true", "nan"))) for left, _ in aligned])
    pair_truth = np.asarray([float(right.get("y_true", right.get("truth", "nan"))) for _, right in aligned])
    if not np.allclose(truth, pair_truth, equal_nan=False):
        raise ValueError("truth values disagree between prediction files")
    point_scores = [float(left.get("prediction", left.get("score", "nan"))) for left, _ in aligned]
    pair_scores = [float(right.get("score", right.get("prediction", "nan"))) for _, right in aligned]
    point_rank = np.asarray(percentile_rank_by_group(point_scores, groups))
    pair_rank = np.asarray(percentile_rank_by_group(pair_scores, groups))
    results = []
    for weight in pairwise_weights:
        if not 0 <= weight <= 1:
            raise ValueError("pairwise weights must be between 0 and 1")
        prediction = (1.0 - weight) * point_rank + weight * pair_rank
        overall = regression_metrics(truth, prediction)
        _, macro, stable_macro, stable_count = macro_metrics(rows, truth, prediction)
        results.append({
            "pairwise_weight": weight,
            "overall": overall,
            "macro_source_spearman": macro,
            "macro_source_spearman_min_n_20": stable_macro,
            "macro_source_count_min_n_20": stable_count,
        })
    return {
        "pointwise_records": len(pointwise_rows), "pairwise_records": len(pairwise_rows),
        "intersection_records": len(aligned), "grouping": "target_id", "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pointwise", type=Path, required=True)
    parser.add_argument("--pairwise", type=Path, required=True)
    parser.add_argument("--pairwise-weights", type=float, nargs="+", default=[index / 10 for index in range(11)])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = sweep_validation_ensemble(read_rows(args.pointwise), read_rows(args.pairwise), args.pairwise_weights)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
