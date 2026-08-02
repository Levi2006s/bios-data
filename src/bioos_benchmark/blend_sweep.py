"""Select an expert blend weight from saved validation predictions."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

from .experiment_train import macro_metrics
from .metrics import regression_metrics


def load_predictions(path: Path, original_blend: float) -> tuple[list[dict[str, str]], np.ndarray, np.ndarray, np.ndarray]:
    if not 0 < original_blend <= 1:
        raise ValueError("original_blend must be greater than 0 and at most 1")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    truth = np.asarray([float(row["truth"]) for row in rows])
    global_prediction = np.asarray([float(row["global_prediction"]) for row in rows])
    if rows and "expert_prediction" in rows[0]:
        expert_prediction = np.asarray([float(row["expert_prediction"]) for row in rows])
    else:
        blended = np.asarray([float(row["prediction"]) for row in rows])
        expert_prediction = (blended - (1.0 - original_blend) * global_prediction) / original_blend
    return rows, truth, global_prediction, expert_prediction


def evaluate_blends(
    rows: list[dict[str, str]],
    truth: np.ndarray,
    global_prediction: np.ndarray,
    expert_prediction: np.ndarray,
    blends: list[float],
) -> list[dict[str, object]]:
    results = []
    for blend in blends:
        if not 0 <= blend <= 1:
            raise ValueError("blend values must be between 0 and 1")
        prediction = np.clip((1.0 - blend) * global_prediction + blend * expert_prediction, 0.0, 1.0)
        overall = regression_metrics(truth, prediction)
        _, macro, stable_macro, stable_count = macro_metrics(rows, truth, prediction)
        results.append({
            "expert_blend": blend,
            "overall": overall,
            "macro_source_spearman": macro,
            "macro_source_spearman_min_n_20": stable_macro,
            "macro_source_count_min_n_20": stable_count,
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--original-blend", type=float, required=True)
    parser.add_argument("--blends", type=float, nargs="+", default=[index / 10 for index in range(11)])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows, truth, global_prediction, expert_prediction = load_predictions(
        args.predictions, args.original_blend
    )
    results = evaluate_blends(rows, truth, global_prediction, expert_prediction, args.blends)
    payload = {"predictions": str(args.predictions), "original_blend": args.original_blend, "results": results}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
