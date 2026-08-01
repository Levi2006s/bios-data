from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Sequence

import numpy as np

from .evaluation import _clean, _prediction_score, _read_unique_csv


def percentile_rank_by_group(
    scores: Sequence[float],
    groups: Sequence[str],
) -> list[float]:
    """Convert scores to tie-aware 0-1 percentile ranks within each group."""
    if len(scores) != len(groups):
        raise ValueError("scores and groups must have the same length.")
    result = [0.5] * len(scores)
    positions: dict[str, list[int]] = defaultdict(list)
    for index, group in enumerate(groups):
        value = float(scores[index])
        if not math.isfinite(value):
            raise ValueError(f"Non-finite score at position {index}.")
        positions[group or "<all>"].append(index)
    for indices in positions.values():
        if len(indices) == 1:
            result[indices[0]] = 0.5
            continue
        ordered = sorted(indices, key=lambda index: (float(scores[index]), index))
        start = 0
        while start < len(ordered):
            end = start + 1
            value = float(scores[ordered[start]])
            while end < len(ordered) and float(scores[ordered[end]]) == value:
                end += 1
            average_rank = (start + end - 1) / 2
            percentile = average_rank / (len(ordered) - 1)
            for position in range(start, end):
                result[ordered[position]] = percentile
            start = end
    return result


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensemble_predictions(
    prediction_paths: Sequence[str | Path],
    output_path: str | Path,
    *,
    weights: Sequence[float] | None = None,
    group_field: str = "target_id",
) -> dict[str, object]:
    """Align predictions by record_id, percentile-normalize, and average."""
    paths = [Path(path) for path in prediction_paths]
    if len(paths) < 2:
        raise ValueError("At least two prediction files are required for an ensemble.")
    models = [_read_unique_csv(path) for path in paths]
    if weights is None:
        normalized_weights = np.full(len(paths), 1.0 / len(paths), dtype=np.float64)
    else:
        if len(weights) != len(paths):
            raise ValueError("weights must match the number of prediction files.")
        normalized_weights = np.asarray(weights, dtype=np.float64)
        if not np.isfinite(normalized_weights).all() or (normalized_weights < 0).any():
            raise ValueError("weights must be finite and non-negative.")
        if normalized_weights.sum() <= 0:
            raise ValueError("At least one weight must be positive.")
        normalized_weights /= normalized_weights.sum()

    reference_lookup = {_clean(row["record_id"]): row for row in models[0]}
    record_ids = sorted(reference_lookup)
    reference_set = set(record_ids)
    aligned_models: list[dict[str, dict[str, str]]] = []
    for path, rows in zip(paths, models):
        lookup = {_clean(row["record_id"]): row for row in rows}
        if set(lookup) != reference_set:
            missing = sorted(reference_set - set(lookup))
            extra = sorted(set(lookup) - reference_set)
            raise ValueError(
                f"{path} record_id mismatch: missing={missing[:5]}, extra={extra[:5]}"
            )
        aligned_models.append(lookup)

    groups = [
        _clean(reference_lookup[record_id].get(group_field)) or "<all>"
        for record_id in record_ids
    ]
    percentile_scores: list[np.ndarray] = []
    model_ids: list[str] = []
    for lookup in aligned_models:
        raw_scores = [_prediction_score(lookup[record_id]) for record_id in record_ids]
        percentile_scores.append(
            np.asarray(percentile_rank_by_group(raw_scores, groups), dtype=np.float64)
        )
        ids = sorted(
            {_clean(row.get("model_id")) or "unknown" for row in lookup.values()}
        )
        model_ids.append("+".join(ids))
    ensemble = np.average(
        np.vstack(percentile_scores),
        axis=0,
        weights=normalized_weights,
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["record_id", "split", "source_group", "target_id", "y_true", "score", "model_id"]
    ensemble_id = "ensemble[" + ",".join(model_ids) + "]"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record_id, score in zip(record_ids, ensemble):
            reference = reference_lookup[record_id]
            writer.writerow(
                {
                    "record_id": record_id,
                    "split": reference.get("split", ""),
                    "source_group": reference.get("source_group", ""),
                    "target_id": reference.get("target_id", ""),
                    "y_true": reference.get("y_true", ""),
                    "score": f"{float(score):.12g}",
                    "model_id": ensemble_id,
                }
            )
    report = {
        "output": str(output_path),
        "records": len(record_ids),
        "group_field": group_field,
        "weights": normalized_weights.tolist(),
        "inputs": [
            {"path": str(path), "sha256": _file_sha256(path), "model_id": model_id}
            for path, model_id in zip(paths, model_ids)
        ],
        "output_sha256": _file_sha256(output_path),
        "score_direction": "larger is better",
    }
    output_path.with_suffix(".summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def scores_to_submission(
    records_path: str | Path,
    predictions_path: str | Path,
    output_path: str | Path,
    *,
    split: str | None = None,
) -> dict[str, object]:
    """Write official VH/VHH, VL, Rank rows with deterministic tie handling."""
    record_rows = _read_unique_csv(Path(records_path))
    prediction_rows = _read_unique_csv(Path(predictions_path))
    if split:
        record_rows = [row for row in record_rows if _clean(row.get("split")) == split]
        prediction_rows = [
            row for row in prediction_rows if not _clean(row.get("split"))
            or _clean(row.get("split")) == split
        ]
        if not record_rows:
            raise ValueError(f"No input rows found for split: {split}")
    prediction_lookup = {_clean(row["record_id"]): row for row in prediction_rows}
    record_ids = {_clean(row["record_id"]) for row in record_rows}
    if set(prediction_lookup) != record_ids:
        missing = sorted(record_ids - set(prediction_lookup))
        extra = sorted(set(prediction_lookup) - record_ids)
        raise ValueError(f"record_id mismatch: missing={missing[:5]}, extra={extra[:5]}")
    ranked = sorted(
        record_rows,
        key=lambda row: (
            -_prediction_score(prediction_lookup[_clean(row["record_id"])]),
            _clean(row["record_id"]),
        ),
    )
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["VH/VHH", "VL", "Rank"])
        writer.writeheader()
        for rank, row in enumerate(ranked, start=1):
            heavy = _clean(row.get("heavy", row.get("VH/VHH")))
            light = _clean(row.get("light", row.get("VL")))
            if not heavy:
                raise ValueError(f"Missing heavy sequence for {_clean(row['record_id'])}")
            writer.writerow({"VH/VHH": heavy, "VL": light, "Rank": rank})
    return {
        "output": str(output_path),
        "records": len(ranked),
        "rank_min": 1 if ranked else None,
        "rank_max": len(ranked) if ranked else None,
        "split_filter": split,
        "output_sha256": _file_sha256(output_path),
    }


def ensemble_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Percentile-rank ensemble for affinity models.")
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--weights", type=float, nargs="*")
    parser.add_argument("--group-field", default="target_id")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def submission_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create the official Bio-OS Rank submission.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split")
    return parser


def main_ensemble() -> None:
    args = ensemble_parser().parse_args()
    report = ensemble_predictions(
        args.inputs,
        args.output,
        weights=args.weights,
        group_field=args.group_field,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main_submission() -> None:
    args = submission_parser().parse_args()
    report = scores_to_submission(
        args.input,
        args.predictions,
        args.output,
        split=args.split,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in {"ensemble", "submit"}:
        raise SystemExit(
            "Usage: python -m bioos_benchmark.ranking.ensemble "
            "{ensemble|submit} [arguments]"
        )
    command = sys.argv[1]
    sys.argv = [sys.argv[0], *sys.argv[2:]]
    if command == "ensemble":
        main_ensemble()
    else:
        main_submission()


if __name__ == "__main__":
    main()
