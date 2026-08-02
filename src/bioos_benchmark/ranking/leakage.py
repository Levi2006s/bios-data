"""Quantify whether ranking performance can be explained by memorization shortcuts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from ..metrics import regression_metrics
from .evaluation import _aligned_rows, _clean, _json_safe, _prediction_score, _read_unique_csv
from .preferences import oriented_label


def _sequence_key(row: Mapping[str, object], *, heavy_only: bool = False) -> str:
    heavy = _clean(row.get("heavy", row.get("VH/VHH")))
    light = "" if heavy_only else _clean(row.get("light", row.get("VL")))
    return hashlib.sha256(f"{heavy}\x1f{light}".encode("utf-8")).hexdigest()


def _metrics(rows: Sequence[tuple[dict[str, str], float, float]]) -> dict[str, object] | None:
    if len(rows) < 2:
        return None
    truth = np.asarray([item[1] for item in rows], dtype=np.float64)
    prediction = np.asarray([item[2] for item in rows], dtype=np.float64)
    return _json_safe(regression_metrics(truth, prediction))


def _memorization_baseline(
    train_rows: Sequence[dict[str, str]],
    evaluation_rows: Sequence[dict[str, str]],
    key_function,
) -> dict[str, object]:
    labels_by_key: dict[str, list[float]] = defaultdict(list)
    all_labels: list[float] = []
    for row in train_rows:
        label = oriented_label(row)
        if label is not None:
            labels_by_key[key_function(row)].append(label)
            all_labels.append(label)
    global_mean = float(np.mean(all_labels)) if all_labels else 0.0
    usable: list[tuple[dict[str, str], float, float]] = []
    seen = 0
    for row in evaluation_rows:
        label = oriented_label(row)
        if label is None:
            continue
        values = labels_by_key.get(key_function(row))
        if values:
            seen += 1
        prediction = float(np.mean(values)) if values else global_mean
        usable.append((row, label, prediction))
    return {
        "seen_rows": seen,
        "seen_fraction": seen / len(usable) if usable else None,
        "fallback": "global training-label mean",
        "metrics": _metrics(usable),
    }


def audit_prediction_shortcuts(
    truth_path: str | Path,
    prediction_path: str | Path,
    *,
    train_split: str = "train",
    evaluation_split: str = "validation",
) -> dict[str, object]:
    truth_rows = _read_unique_csv(Path(truth_path))
    prediction_rows = _read_unique_csv(Path(prediction_path))
    train_rows = [row for row in truth_rows if _clean(row.get("split")) == train_split]
    evaluation_rows = [
        row for row in truth_rows if _clean(row.get("split")) == evaluation_split
    ]
    evaluation_predictions = [
        row
        for row in prediction_rows
        if not _clean(row.get("split")) or _clean(row.get("split")) == evaluation_split
    ]
    if not train_rows or not evaluation_rows:
        raise ValueError("Both training and evaluation splits must be non-empty.")
    aligned = _aligned_rows(evaluation_rows, evaluation_predictions)
    scored: list[tuple[dict[str, str], float, float]] = []
    for row, prediction_row in aligned:
        label = oriented_label(row)
        if label is not None:
            scored.append((row, label, _prediction_score(prediction_row)))

    train_exact = {_sequence_key(row) for row in train_rows}
    train_heavy = {_sequence_key(row, heavy_only=True) for row in train_rows}
    train_sources = {_clean(row.get("source_group")) for row in train_rows}
    train_files = {_clean(row.get("source_file")) for row in train_rows}
    seen_exact = [item for item in scored if _sequence_key(item[0]) in train_exact]
    novel_exact = [item for item in scored if _sequence_key(item[0]) not in train_exact]
    seen_source = [item for item in scored if _clean(item[0].get("source_group")) in train_sources]
    novel_source = [item for item in scored if _clean(item[0].get("source_group")) not in train_sources]

    exact_baseline = _memorization_baseline(train_rows, evaluation_rows, _sequence_key)
    source_baseline = _memorization_baseline(
        train_rows, evaluation_rows, lambda row: _clean(row.get("source_group"))
    )
    overlap = {
        "exact_antibody_rows": len(seen_exact),
        "exact_antibody_fraction": len(seen_exact) / len(scored) if scored else None,
        "heavy_chain_rows": sum(_sequence_key(item[0], heavy_only=True) in train_heavy for item in scored),
        "source_group_rows": len(seen_source),
        "source_group_fraction": len(seen_source) / len(scored) if scored else None,
        "source_file_rows": sum(_clean(item[0].get("source_file")) in train_files for item in scored),
    }
    warnings: list[str] = []
    if overlap["exact_antibody_rows"]:
        warnings.append("Some evaluation antibodies occur exactly in training; inspect novel-only metrics.")
    if overlap["source_group_rows"]:
        warnings.append("Some evaluation rows share a source group with training.")
    if not warnings:
        warnings.append("No exact-antibody or source-group overlap was detected for this split.")
    report = {
        "truth": str(truth_path),
        "predictions": str(prediction_path),
        "train_split": train_split,
        "evaluation_split": evaluation_split,
        "train_rows": len(train_rows),
        "evaluation_rows": len(scored),
        "overlap": overlap,
        "model_metrics": {
            "all": _metrics(scored),
            "seen_exact_antibody": _metrics(seen_exact),
            "novel_exact_antibody": _metrics(novel_exact),
            "seen_source": _metrics(seen_source),
            "novel_source": _metrics(novel_source),
        },
        "memorization_baselines": {
            "exact_antibody_lookup": exact_baseline,
            "source_group_mean": source_baseline,
        },
        "feature_contract": {
            "uses_sequence": ["heavy", "light", "antigen_seq"],
            "uses_source_metadata": False,
            "excluded_from_model_features": ["source_group", "source_file", "paper_title", "record_id"],
        },
        "interpretation_warnings": warnings,
    }
    return _json_safe(report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit duplicate and source memorization shortcuts.")
    parser.add_argument("--truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-split", default="train")
    parser.add_argument("--evaluation-split", default="validation")
    args = parser.parse_args()
    report = audit_prediction_shortcuts(
        args.truth,
        args.predictions,
        train_split=args.train_split,
        evaluation_split=args.evaluation_split,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
